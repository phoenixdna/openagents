"""
Werewolf Game Host Mod - Hardcoded Logic Version v4

Key Fix: Only process messages from the ORIGINAL sender, not notifications.
The notification events are sent to each agent individually, but we only
want to process the message ONCE.

Event Flow:
1. Player sends message -> thread.channel_message.send (we should handle this)
2. Messaging mod broadcasts -> thread.channel_message.notification (to each agent)
   We should IGNORE these notifications since they are just echoes.
"""

import logging
import asyncio
import random
import re
from enum import Enum, auto
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field

from openagents.core.base_mod import BaseMod, mod_event_handler
from openagents.models.event import Event, EventVisibility
from openagents.models.event_response import EventResponse

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    WAITING = auto()
    NIGHT_WOLF = auto()
    NIGHT_WITCH = auto()
    NIGHT_SEER = auto()
    DAY_ANNOUNCE = auto()
    DAY_SPEECH = auto()
    DAY_VOTE = auto()
    LAST_WORDS = auto()
    GAME_OVER = auto()


class ActionType(Enum):
    KILL = "kill"
    SAVE = "save"
    POISON = "poison"
    CHECK = "check"
    VOTE = "vote"
    SPEECH = "speech"
    SKIP = "skip"
    START_GAME = "start_game"
    RESTART = "restart"
    UNKNOWN = "unknown"


@dataclass
class PlayerInfo:
    name: str
    agent_id: str
    role: str = ""
    alive: bool = True
    number: int = 0


@dataclass
class GameState:
    phase: GamePhase = GamePhase.WAITING
    channel: str = "werewolf-game"
    day_number: int = 0
    night_number: int = 0
    
    players: Dict[str, PlayerInfo] = field(default_factory=dict)
    
    wolf_votes: Dict[str, str] = field(default_factory=dict)
    wolf_target: Optional[str] = None
    witch_saved: bool = False
    witch_poisoned: Optional[str] = None
    
    witch_has_antidote: bool = True
    witch_has_poison: bool = True
    
    speech_queue: List[str] = field(default_factory=list)
    current_speaker: Optional[str] = None
    votes: Dict[str, str] = field(default_factory=dict)
    
    last_night_deaths: List[str] = field(default_factory=list)
    
    last_words_queue: List[str] = field(default_factory=list)
    next_phase_after_last_words: str = "night"


class IntentParser:
    @staticmethod
    def parse(text: str, alive_players: List[str]) -> Tuple[ActionType, Optional[str]]:
        text = text.strip()
        
        # Ignore Host system messages (prevent self-loop)
        if text.startswith("🎮") or text.startswith("⚠️") or text.startswith("🔒"):
            return (ActionType.UNKNOWN, None)
            
        text_lower = text.lower()
        
        # Restart command
        if "强制重开" in text or text_lower == "restart" or "重开游戏" in text:
            return (ActionType.RESTART, None)
        
        # Start command - must be short to avoid matching long sentences
        if len(text) < 20 and ("游戏开始" in text_lower or "开始游戏" in text_lower or text_lower == "start"):
            return (ActionType.START_GAME, None)
        
        for pattern in [r"(?:杀|刀|击杀)\s*(.+)", r"kill\s+(.+)"]:
            match = re.search(pattern, text)
            if match:
                target = IntentParser._match_player(match.group(1), alive_players)
                if target:
                    return (ActionType.KILL, target)
        
        if any(w in text for w in ["救", "save", "解药"]) and "不" not in text:
            return (ActionType.SAVE, None)
        
        for pattern in [r"(?:毒|毒杀|poison)\s*(.+)"]:
            match = re.search(pattern, text)
            if match:
                target = IntentParser._match_player(match.group(1), alive_players)
                if target:
                    return (ActionType.POISON, target)
        
        for pattern in [r"(?:查验|查|检查|check)\s*(.+)"]:
            match = re.search(pattern, text)
            if match:
                target = IntentParser._match_player(match.group(1), alive_players)
                if target:
                    return (ActionType.CHECK, target)
        
        for pattern in [r"(?:投|投票|vote)\s*(.+)"]:
            match = re.search(pattern, text)
            if match:
                target = IntentParser._match_player(match.group(1), alive_players)
                if target:
                    return (ActionType.VOTE, target)
        
        if any(w in text for w in ["不", "跳过", "skip", "pass", "放弃", "不使用", "不救"]):
            return (ActionType.SKIP, None)
        
        for player in alive_players:
            if player.lower() in text or text in player.lower():
                return (ActionType.UNKNOWN, player)
        
        return (ActionType.SPEECH, text)
    
    @staticmethod
    def _match_player(text: str, players: List[str]) -> Optional[str]:
        text = text.strip()
        for p in players:
            if text == p.lower() or text in p.lower() or p.lower() in text:
                return p
        num_match = re.search(r"(\d+)", text)
        if num_match:
            num = num_match.group(1)
            for p in players:
                if num in p:
                    return p
        return None


class WerewolfNetworkMod(BaseMod):
    """Werewolf game Host with hardcoded logic."""
    
    requires_adapter = False
    
    ROLES = ["wolf", "wolf", "villager", "villager", "seer", "witch"]
    ROLE_NAMES = {"wolf": "狼人", "villager": "村民", "seer": "预言家", "witch": "女巫"}    # Game Settings
    TIMEOUT_SECONDS = 15  # Reverted to 15s per user request
    MAX_SPEECH_LENGTH = 240
    
    def __init__(self, mod_name: str = "openagents.mods.games.werewolf"):
        super().__init__(mod_name)
        self.game_channel = "werewolf-game"
        self.state: Optional[GameState] = None
        self.agent_to_player: Dict[str, str] = {}
        self.player_to_agent: Dict[str, str] = {}
        self.timers: Dict[str, asyncio.Task] = {}
        self.processed_events: Set[str] = set()
        self.game_starting: bool = False  # Lock to prevent multiple starts

    async def initialize(self) -> None:
        print("\n" + "=" * 60)
        print("🐺 WEREWOLF HOST MOD - HARDCODED v4.0")
        print("   (Fixed event deduplication)")
        print("=" * 60 + "\n")
        logger.info("[Werewolf] Host mod initialized v4")

    # ========================================================
    # EVENT HANDLERS
    # Handle thread.channel_message.send (original message)
    # NOT thread.channel_message.notification (echoes to each agent)
    # ========================================================

    @mod_event_handler("thread.channel_message.notification")
    async def handle_channel_notification(self, event: Event) -> Optional[EventResponse]:
        """Handle channel message notifications (deduplicated)."""
        try:
            payload = event.payload or {}
            channel = payload.get("channel", "")
            source = event.source_id
            
            if channel != self.game_channel:
                return None
            
            # Skip our own messages (check source_id AND sender_name)
            sender_name = payload.get("sender_name", "")
            if source == "werewolf_host" or sender_name == "🎮 主持人" or source == "host":
                return None
            
            # Get message text
            text = payload.get("text", "")
            if not text:
                content = payload.get("content", {})
                text = content.get("text", "") if isinstance(content, dict) else str(content)
            
            if not text:
                return None
            
            # Deduplicate by original event ID if available, else event ID
            event_id = payload.get("original_event_id", event.id)
            if event_id in self.processed_events:
                return None
            self.processed_events.add(event_id)
            
            logger.info(f"[Werewolf] 📥 Channel msg from {source}: {text[:50]}...")
            await self._process_input(source, text, is_dm=False)
            return None
        except Exception as e:
            logger.error(f"[Werewolf] Error in handle_channel_notification: {e}", exc_info=True)
            return None

    @mod_event_handler("thread.direct_message.notification")  
    async def handle_dm_notification(self, event: Event) -> Optional[EventResponse]:
        """Handle DM notifications (from players TO host)."""
        try:
            payload = event.payload or {}
            source = event.source_id
            dest = event.destination_id
            
            # Only handle DMs sent TO the host
            if dest != "werewolf_host":
                return None
            
            if source == "werewolf_host":
                return None
            
            content = payload.get("content", {})
            text = content.get("text", "") if isinstance(content, dict) else str(content)
            
            if not text:
                text = payload.get("text", "")
            
            if not text:
                return None
            
            # Deduplicate
            event_id = payload.get("original_event_id", event.id)
            if event_id in self.processed_events:
                return None
            self.processed_events.add(event_id)
            
            logger.info(f"[Werewolf] 📨 DM from {source}: {text[:50]}...")
            await self._process_input(source, text, is_dm=True)
            return None
        except Exception as e:
            logger.error(f"[Werewolf] Error in handle_dm_notification: {e}", exc_info=True)
            return None



    # ========================================================
    # INPUT PROCESSING
    # ========================================================

    async def _process_input(self, sender_id: str, text: str, is_dm: bool):
        player_name = self.agent_to_player.get(sender_id)
        alive = self._get_alive_players() if self.state else []
        action, target = IntentParser.parse(text, alive)
        
        logger.info(f"[Werewolf] 🎯 Parsed: {action.name}, target={target}")
        
        if action == ActionType.START_GAME:
            # Only allow start if game is not running
            if self.state and self.state.phase not in [GamePhase.WAITING, GamePhase.GAME_OVER]:
                await self._broadcast("⚠️ 游戏正在进行中。如需重开请发送「强制重开」。")
                return
                
            if self.game_starting:
                logger.info("[Werewolf] Game already starting, ignoring duplicate")
                return
            await self._start_game(sender_id)
            return
            
        if action == ActionType.RESTART:
            await self._start_game(sender_id)
            return
        
        if not self.state or self.state.phase == GamePhase.WAITING:
            if not self.game_starting:
                await self._broadcast("⚠️ 游戏尚未开始。发送 **游戏开始** 来开始游戏。")
            return
        
        if not player_name:
            return
        
        player = self.state.players.get(player_name)
        if not player:
            return
            
        # Dead players can only act in LAST_WORDS phase
        if not player.alive and self.state.phase != GamePhase.LAST_WORDS:
            return
        
        phase = self.state.phase
        
        if phase == GamePhase.NIGHT_WOLF:
            await self._handle_wolf_action(player, action, target, text)
        elif phase == GamePhase.NIGHT_WITCH:
            await self._handle_witch_action(player, action, target, text)
        elif phase == GamePhase.NIGHT_SEER:
            await self._handle_seer_action(player, action, target)
        elif phase == GamePhase.DAY_SPEECH:
            await self._handle_speech(player, text)
        elif phase == GamePhase.LAST_WORDS:
            await self._handle_last_words(player, text)
        elif phase == GamePhase.DAY_VOTE:
            await self._handle_vote(player, action, target)

    # ========================================================
    # GAME START
    # ========================================================

    async def _start_game(self, initiator_id: str):
        """Start game immediately."""
        if self.game_starting:
            return
        
        self.game_starting = True
        logger.info("[Werewolf] 🎮 Starting new game...")
        
        self.state = GameState(channel=self.game_channel)
        self.agent_to_player.clear()
        self.player_to_agent.clear()
        # self.processed_events.clear()  <-- Removed to prevent loop
        
        # Add human player
        self._add_player("玩家", initiator_id)
        
        # Add AI players - IDs must match YAML configs exactly
        ai_configs = [
            ("张三", "ai_player_张三"),
            ("李四", "ai_player_李四"),
            ("王五", "ai_player_王五"),
            ("赵六", "ai_player_赵六"),
            ("钱七", "ai_player_钱七"),
        ]
        for name, agent_id in ai_configs:
            self._add_player(name, agent_id)
        
        # Assign roles
        self._assign_roles()
        
        # Announce
        await self._broadcast(
            f"🎮 **游戏开始！**\n\n"
            f"👤 您: 玩家\n"
            f"🤖 AI玩家: 张三, 李四, 王五, 赵六, 钱七\n\n"
            f"🎲 角色分配完成！\n"
            f"本局配置: 狼人×2, 村民×2, 预言家×1, 女巫×1\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Notify roles privately
        await self._notify_roles()
        
        # Start first night after a delay
        await asyncio.sleep(2)
        self.game_starting = False
        await self._start_night()

    def _add_player(self, name: str, agent_id: str):
        number = len(self.state.players) + 1
        self.state.players[name] = PlayerInfo(name=name, agent_id=agent_id, number=number)
        self.agent_to_player[agent_id] = name
        self.player_to_agent[name] = agent_id
        logger.info(f"[Werewolf] Player {name} -> {agent_id}")

    def _assign_roles(self):
        roles = self.ROLES.copy()
        random.shuffle(roles)
        for i, (name, player) in enumerate(self.state.players.items()):
            player.role = roles[i]
            logger.info(f"[Werewolf] {name} = {self.ROLE_NAMES[roles[i]]}")

    async def _notify_roles(self):
        wolves = [p.name for p in self.state.players.values() if p.role == "wolf"]
        
        for name, player in self.state.players.items():
            role_cn = self.ROLE_NAMES[player.role]
            msg = f"🎭 你的角色是 **{role_cn}**\n"
            
            if player.role == "wolf":
                teammate = [w for w in wolves if w != name]
                if teammate:
                    msg += f"🐺 你的狼人队友: {teammate[0]}\n"
                msg += "技能: 每晚与其他狼人讨论并投票杀死一名玩家"
            elif player.role == "seer":
                msg += "🔮 技能: 每晚可以查验一名玩家的身份"
            elif player.role == "witch":
                msg += "💊 技能: 拥有解药和毒药各一瓶"
            else:
                msg += "技能: 普通村民，没有特殊能力"
            
            await self._send_dm(player.agent_id, msg)

    # ========================================================
    # NIGHT PHASE
    # ========================================================

    async def _start_night(self):
        self.state.night_number += 1
        self.state.wolf_votes.clear()
        self.state.wolf_target = None
        self.state.witch_saved = False
        self.state.witch_poisoned = None
        
        await self._broadcast(f"🌙 **第 {self.state.night_number} 夜降临**\n天黑请闭眼...\n━━━━━━━━━━━━━━━━━━━━")
        await asyncio.sleep(1)
        await self._start_wolf_phase()

    async def _start_wolf_phase(self):
        logger.info("[Werewolf] Starting Wolf Phase...")
        self.state.phase = GamePhase.NIGHT_WOLF
        
        wolves = [p for p in self.state.players.values() if p.role == "wolf" and p.alive]
        logger.info(f"[Werewolf] Wolves: {[w.name for w in wolves]}")
        
        if not wolves:
            logger.info("[Werewolf] No wolves, skipping to witch")
            await self._start_witch_phase()
            return
        
        targets = [p.name for p in self.state.players.values() if p.role != "wolf" and p.alive]
        targets_str = ", ".join(targets)
        
        for wolf in wolves:
            try:
                other_wolves = [w.name for w in wolves if w.name != wolf.name]
                teammate_str = other_wolves[0] if other_wolves else "无"
                
                msg = (
                    f"🐺 **狼人行动**\n\n"
                    f"你的队友: {teammate_str}\n"
                    f"当前可击杀: {targets_str}\n\n"
                    f"💬 **讨论**：直接回复消息可与队友沟通。\n"
                    f"🔪 **击杀**：回复「杀 [玩家名]」进行投票。"
                )
                logger.info(f"[Werewolf] Sending Wolf DM to {wolf.agent_id}...")
                await self._send_dm(wolf.agent_id, msg)
            except Exception as e:
                logger.error(f"[Werewolf] Failed to send DM to wolf {wolf.name}: {e}")
        
        self._set_timer("wolf", self.TIMEOUT_SECONDS, self._wolf_timeout)

    async def _handle_wolf_action(self, player: PlayerInfo, action: ActionType, 
                                   target: Optional[str], text: str):
        if player.role != "wolf":
            return
        
        # Forward to teammates
        wolves = [p for p in self.state.players.values() 
                  if p.role == "wolf" and p.alive and p.name != player.name]
        for wolf in wolves:
            await self._send_dm(wolf.agent_id, f"🐺 队友 {player.name}: {text}")
        
        if target:
            target_player = self.state.players.get(target)
            if target_player and target_player.role != "wolf" and target_player.alive:
                self.state.wolf_votes[player.name] = target
                await self._send_dm(player.agent_id, f"✅ 已选择击杀: {target}")
                
                alive_wolves = [p.name for p in self.state.players.values() if p.role == "wolf" and p.alive]
                if len(self.state.wolf_votes) >= len(alive_wolves):
                    self._cancel_timer("wolf")
                    await self._finalize_wolf_kill()

    async def _wolf_timeout(self):
        wolves = [p for p in self.state.players.values() if p.role == "wolf" and p.alive]
        missing = [w for w in wolves if w.name not in self.state.wolf_votes]
        
        # Check if any missing wolf is HUMAN
        has_human = any(not w.agent_id.startswith("ai_player_") for w in missing)
        
        if has_human:
            logger.info("[Werewolf] Wolf timeout - blocking for HUMAN")
            msg = f"⏳ 等待以下狼人行动: {', '.join([p.name for p in missing])}"
            for wolf in wolves:
                 await self._send_dm(wolf.agent_id, msg)
            self._set_timer("wolf", self.TIMEOUT_SECONDS, self._wolf_timeout)
        else:
            logger.info("[Werewolf] Wolf timeout - AI auto-resolve")
            # If all missing are AI, we can proceed (or random vote)
            # For simplicity, if AI fails to vote, we skip their vote or random
            # Logic: finalize kill based on existing votes or random
            if self.state.wolf_votes:
                 target = list(self.state.wolf_votes.values())[0]
            else:
                 candidates = [p.name for p in self.state.players.values() if p.role != "wolf" and p.alive]
                 target = random.choice(candidates) if candidates else None
            
            if target:
                self.state.wolf_target = target
            await self._start_witch_phase()

    async def _finalize_wolf_kill(self):
        if self.state.wolf_votes:
            votes = list(self.state.wolf_votes.values())
            self.state.wolf_target = max(set(votes), key=votes.count)
        await self._start_witch_phase()

    async def _start_witch_phase(self):
        self.state.phase = GamePhase.NIGHT_WITCH
        
        witch = next((p for p in self.state.players.values() if p.role == "witch" and p.alive), None)
        if not witch:
            await self._start_seer_phase()
            return
        
        msg = "💊 **女巫行动**\n\n"
        
        if self.state.wolf_target and self.state.witch_has_antidote:
            msg += f"🩸 今晚 **{self.state.wolf_target}** 被狼人杀害了！\n"
            msg += "回复「救」使用解药救活他。\n\n"
        elif self.state.witch_has_antidote:
            msg += "今晚无人被杀。\n\n"
        else:
            msg += "解药已用完。\n\n"
        
        if self.state.witch_has_poison:
            alive = [p.name for p in self.state.players.values() if p.alive and p.name != witch.name]
            msg += f"毒药可用，回复「毒 [玩家名]」使用。\n可选: {', '.join(alive)}\n\n"
        
        msg += "回复「不使用」跳过。"
        
        await self._send_dm(witch.agent_id, msg)
        self._set_timer("witch", self.TIMEOUT_SECONDS, self._witch_timeout)

    async def _handle_witch_action(self, player: PlayerInfo, action: ActionType,
                                    target: Optional[str], text: str):
        if player.role != "witch":
            return
        
        should_advance = False
        
        if action == ActionType.SAVE:
            if self.state.witch_has_antidote and self.state.wolf_target:
                self.state.witch_saved = True
                self.state.witch_has_antidote = False
                await self._send_dm(player.agent_id, f"💊 已救下 {self.state.wolf_target}")
                should_advance = True
        elif action == ActionType.POISON and target:
            if self.state.witch_has_poison:
                target_player = self.state.players.get(target)
                if target_player and target_player.alive:
                    self.state.witch_poisoned = target
                    self.state.witch_has_poison = False
                    await self._send_dm(player.agent_id, f"☠️ 已毒杀 {target}")
                    should_advance = True
        elif action == ActionType.SKIP:
            await self._send_dm(player.agent_id, "✅ 跳过")
            should_advance = True
        
        if should_advance:
            self._cancel_timer("witch")
            await self._start_seer_phase()

    async def _witch_timeout(self):
        witch = next((p for p in self.state.players.values() if p.role == "witch" and p.alive), None)
        if witch:
            if not witch.agent_id.startswith("ai_player_"):
                logger.info("[Werewolf] Witch timeout - blocking for HUMAN")
                await self._send_dm(witch.agent_id, "⏳ 请女巫尽快行动 (或回复「不使用」跳过)")
                self._set_timer("witch", self.TIMEOUT_SECONDS, self._witch_timeout)
                return
        
        logger.info("[Werewolf] Witch timeout - AI skip")
        await self._start_seer_phase()

    async def _start_seer_phase(self):
        self.state.phase = GamePhase.NIGHT_SEER
        
        seer = next((p for p in self.state.players.values() if p.role == "seer" and p.alive), None)
        if not seer:
            await self._resolve_night()
            return
        
        alive = [p.name for p in self.state.players.values() if p.alive and p.name != seer.name]
        
        msg = (
            f"🔮 **预言家行动**\n\n"
            f"可查验: {', '.join(alive)}\n\n"
            f"回复「查验 [玩家名]」"
        )
        
        await self._send_dm(seer.agent_id, msg)
        self._set_timer("seer", self.TIMEOUT_SECONDS, self._seer_timeout)

    async def _handle_seer_action(self, player: PlayerInfo, action: ActionType, target: Optional[str]):
        if player.role != "seer":
            return
        
        if target:
            target_player = self.state.players.get(target)
            if target_player:
                is_wolf = target_player.role == "wolf"
                result = "🐺 狼人 (坏人)" if is_wolf else "👤 好人 (非狼人)"
                await self._send_dm(player.agent_id, f"🔮 查验结果：\n**{target}** 是 {result}")
                self._cancel_timer("seer")
                await self._resolve_night()

    async def _seer_timeout(self):
        seer = next((p for p in self.state.players.values() if p.role == "seer" and p.alive), None)
        if seer:
            if not seer.agent_id.startswith("ai_player_"):
                logger.info("[Werewolf] Seer timeout - blocking for HUMAN")
                await self._send_dm(seer.agent_id, "⏳ 请预言家尽快查验")
                self._set_timer("seer", self.TIMEOUT_SECONDS, self._seer_timeout)
                return

        logger.info("[Werewolf] Seer timeout - AI skip")
        await self._resolve_night()

    # ========================================================
    # NIGHT RESOLUTION
    # ========================================================

    async def _resolve_night(self):
        logger.info("[Werewolf] Resolving night...")
        deaths = []
        
        if self.state.wolf_target and not self.state.witch_saved:
            deaths.append(self.state.wolf_target)
            self.state.players[self.state.wolf_target].alive = False
        
        if self.state.witch_poisoned:
            if self.state.witch_poisoned not in deaths:
                deaths.append(self.state.witch_poisoned)
                self.state.players[self.state.witch_poisoned].alive = False
        
        self.state.last_night_deaths = deaths
        
        winner = self._check_victory()
        if winner:
            await self._end_game(winner)
            return
        
        await self._start_day(deaths)

    # ========================================================
    # DAY PHASE
    # ========================================================

    async def _start_day(self, deaths: List[str]):
        self.state.day_number += 1
        self.state.phase = GamePhase.DAY_ANNOUNCE
        
        msg = f"☀️ **第 {self.state.day_number} 天**\n"
        if deaths:
            msg += "昨晚死亡: " + ", ".join([f"💀{d}" for d in deaths])
        else:
            msg += "🌈 平安夜，无人死亡"
        msg += "\n━━━━━━━━━━━━━━━━━━━━"
        
        await self._broadcast(msg)
        await asyncio.sleep(1)
        
        # Night 1 Death -> Last Words
        if self.state.day_number == 1 and deaths:
            self.state.last_words_queue = deaths.copy()
            self.state.next_phase_after_last_words = "speech"
            await self._start_last_words(self.state.last_words_queue.pop(0))
        else:
            await self._start_speech_phase()

    async def _start_speech_phase(self):
        self.state.phase = GamePhase.DAY_SPEECH
        
        alive = [p.name for p in self.state.players.values() if p.alive]
        random.shuffle(alive)
        self.state.speech_queue = alive.copy()
        
        await self._broadcast("📢 **发言环节**")
        await self._prompt_next_speaker()

    async def _prompt_next_speaker(self):
        if not self.state.speech_queue:
            await self._start_vote_phase()
            return
        
        speaker = self.state.speech_queue.pop(0)
        self.state.current_speaker = speaker
        
        await self._broadcast(f"👉 **{speaker}** 请发言")
        
        player = self.state.players.get(speaker)
        if player:
            await self._send_dm(player.agent_id, f"🎤 轮到你发言（上限{self.MAX_SPEECH_LENGTH}字）")
        
        self._set_timer("speech", self.TIMEOUT_SECONDS, self._speech_timeout)

    async def _handle_speech(self, player: PlayerInfo, text: str):
        if player.name != self.state.current_speaker:
            return
        
        speech = text[:self.MAX_SPEECH_LENGTH]
        if len(text) > self.MAX_SPEECH_LENGTH:
            speech += "..."
        
        await self._broadcast(f"💬 **{player.name}**: {speech}")
        
        self._cancel_timer("speech")
        self.state.current_speaker = None
        
        await asyncio.sleep(1)
        await self._prompt_next_speaker()

    async def _speech_timeout(self):
        if self.state.current_speaker:
            player = self.state.players.get(self.state.current_speaker)
            
            if player and not player.agent_id.startswith("ai_player_"):
                # Human blocking
                await self._broadcast(f"⏳ 等待 **{self.state.current_speaker}** 发言...")
                await self._send_dm(player.agent_id, "⏳ 请尽快发言")
                self._set_timer("speech", self.TIMEOUT_SECONDS, self._speech_timeout)
                return
            
            # AI skip
            await self._broadcast(f"⏰ {self.state.current_speaker} 超时跳过")
            self.state.current_speaker = None
            await self._prompt_next_speaker()
            
    # ========================================================
    # LAST WORDS PHASE
    # ========================================================

    async def _start_last_words(self, player_name: str):
        self.state.phase = GamePhase.LAST_WORDS
        self.state.current_speaker = player_name
        
        await self._broadcast(f"🎤 请 **{player_name}** 发表遗言（上限{self.MAX_SPEECH_LENGTH}字）")
        
        player = self.state.players.get(player_name)
        if player:
            await self._send_dm(player.agent_id, f"🎤 请发表你的遗言")
        
        self._set_timer("last_words", self.TIMEOUT_SECONDS, self._last_words_timeout)

    async def _handle_last_words(self, player: PlayerInfo, text: str):
        if player.name != self.state.current_speaker:
            return
            
        speech = text[:self.MAX_SPEECH_LENGTH]
        await self._broadcast(f"💬 **{player.name}** (遗言): {speech}")
        
        self._cancel_timer("last_words")
        self.state.current_speaker = None
        
        await asyncio.sleep(2)
        
        # Check queue
        if hasattr(self.state, 'last_words_queue') and self.state.last_words_queue:
            next_player = self.state.last_words_queue.pop(0)
            await self._start_last_words(next_player)
            return

        # Go to next phase
        next_phase = getattr(self.state, 'next_phase_after_last_words', 'night')
        if next_phase == "speech":
            await self._start_speech_phase()
        else:
            await self._start_night()

    async def _last_words_timeout(self):
        # ... existing logic ...
        if self.state.current_speaker:
             player = self.state.players.get(self.state.current_speaker)
             if player and not player.agent_id.startswith("ai_player_"):
                 # ... existing blocking logic ...
                 await self._broadcast(f"⏳ 等待 **{self.state.current_speaker}** 发表遗言...")
                 self._set_timer("last_words", self.TIMEOUT_SECONDS, self._last_words_timeout)
                 return
        
        # AI skip
        await self._broadcast("⏰ 遗言超时")
        self.state.current_speaker = None
        
        # Check queue logic (same as handle_last_words)
        if hasattr(self.state, 'last_words_queue') and self.state.last_words_queue:
            next_player = self.state.last_words_queue.pop(0)
            await self._start_last_words(next_player)
            return

        next_phase = getattr(self.state, 'next_phase_after_last_words', 'night')
        if next_phase == "speech":
            await self._start_speech_phase()
        else:
            await self._start_night()

    async def _start_vote_phase(self):
        self.state.phase = GamePhase.DAY_VOTE
        self.state.votes.clear()
        
        alive = [p.name for p in self.state.players.values() if p.alive]
        
        await self._broadcast(f"🗳️ **投票** | 候选: {', '.join(alive)}")
        
        for name in alive:
            player = self.state.players.get(name)
            if player:
                candidates = [p for p in alive if p != name]
                await self._send_dm(player.agent_id, f"🗳️ 投票: 回复「投票 [玩家名]」\n可选: {', '.join(candidates)}")
        
        self._set_timer("vote", self.TIMEOUT_SECONDS, self._vote_timeout)

    async def _handle_vote(self, player: PlayerInfo, action: ActionType, target: Optional[str]):
        if player.name in self.state.votes:
            return
        
        if target and target in [p.name for p in self.state.players.values() if p.alive]:
            self.state.votes[player.name] = target
            await self._broadcast(f"🗳️ {player.name} 已投票")
            
            alive = [p.name for p in self.state.players.values() if p.alive]
            if len(self.state.votes) >= len(alive):
                self._cancel_timer("vote")
                await self._resolve_vote()

    async def _vote_timeout(self):
        alive = [p for p in self.state.players.values() if p.alive]
        missing = [p for p in alive if p.name not in self.state.votes]
        
        has_human = any(not p.agent_id.startswith("ai_player_") for p in missing)
        
        if has_human:
            logger.info("[Werewolf] Vote timeout - blocking for HUMAN")
            missing_names = [p.name for p in missing]
            await self._broadcast(f"⏳ 等待以下玩家投票: {', '.join(missing_names)}")
            
            for p in missing:
                player = self.state.players.get(p.name)
                if player:
                    candidates = [x.name for x in alive if x.name != p.name]
                    await self._send_dm(player.agent_id, f"🗳️ 请投票！候选: {', '.join(candidates)}")
            
            self._set_timer("vote", self.TIMEOUT_SECONDS, self._vote_timeout)
        else:
            logger.info("[Werewolf] Vote timeout - AI auto-resolve")
            # Auto-vote for AI
            for p in missing:
                candidates = [x.name for x in alive if x.name != p.name]
                if candidates:
                    target = random.choice(candidates)
                    self.state.votes[p.name] = target
                    await self._broadcast(f"🤖 {p.name} (AI) 自动投票")
            
            await self._resolve_vote()

    async def _resolve_vote(self):
        if not self.state.votes:
            await self._broadcast("⚖️ 无人投票，无人出局")
        else:
            counts = {}
            for target in self.state.votes.values():
                counts[target] = counts.get(target, 0) + 1
            
            results = ", ".join([f"{k}:{v}票" for k, v in counts.items()])
            await self._broadcast(f"📊 结果: {results}")
            
            max_votes = max(counts.values())
            leaders = [k for k, v in counts.items() if v == max_votes]
            
            if len(leaders) > 1:
                await self._broadcast("⚖️ 平票，无人出局")
            else:
                eliminated = leaders[0]
                player = self.state.players[eliminated]
                player.alive = False
                role = self.ROLE_NAMES[player.role]
                await self._broadcast(f"👋 **{eliminated}** 出局 | 身份: {role}")
                
                # Check win before last words
                winner = self._check_victory()
                if winner:
                    await self._end_game(winner)
                    return
                
                # Go to last words
                self.state.last_words_queue = [] # clear queue just in case
                self.state.next_phase_after_last_words = "night"
                await self._start_last_words(eliminated)
                return

        winner = self._check_victory()
        if winner:
            await self._end_game(winner)
            return
        
        await asyncio.sleep(2)
        await self._start_night()

    # ========================================================
    # VICTORY & END
    # ========================================================

    def _check_victory(self) -> Optional[str]:
        alive = [p for p in self.state.players.values() if p.alive]
        wolves = [p for p in alive if p.role == "wolf"]
        villagers = [p for p in alive if p.role != "wolf"]
        
        if not wolves:
            return "villager"
        if len(wolves) >= len(villagers):
            return "wolf"
        return None

    async def _end_game(self, winner: str):
        self.state.phase = GamePhase.GAME_OVER
        
        msg = "🐺 **狼人胜利！** (屠城)" if winner == "wolf" else "👥 **好人胜利！** (狼人全灭)"
        
        alive = [p for p in self.state.players.values() if p.alive]
        dead = [p for p in self.state.players.values() if not p.alive]
        
        alive_str = ", ".join([f"{p.name}({self.ROLE_NAMES[p.role]})" for p in alive])
        dead_str = ", ".join([f"{p.name}({self.ROLE_NAMES[p.role]})" for p in dead])
        
        stats = (
            f"✅ **幸存者**: {alive_str if alive_str else '无'}\n"
            f"💀 **牺牲者**: {dead_str if dead_str else '无'}"
        )
        
        await self._broadcast(f"🏁 **游戏结束**\n\n{msg}\n\n{stats}")
        
        # Reset state
        self.state = None
        self.game_starting = False

    # ========================================================
    # UTILITIES
    # ========================================================

    def _get_alive_players(self) -> List[str]:
        if not self.state:
            return []
        return [p.name for p in self.state.players.values() if p.alive]

    async def _broadcast(self, text: str):
        """Broadcast to channel."""
        if not self.network:
            logger.error("[Werewolf] No network!")
            return
        
        event = Event(
            event_name="thread.channel_message.post",
            source_id="werewolf_host",
            payload={
                "channel": self.game_channel,
                "content": {"text": text},
                "message_type": "channel_message",
                "sender_name": "🎮 主持人",
                "is_system_message": True
            },
            visibility=EventVisibility.CHANNEL,
            channel=self.game_channel
        )
        await self.send_event(event)
        logger.info(f"[Werewolf] 📤 {text[:40]}...")

    async def _send_dm(self, agent_id: str, text: str):
        """Send DM."""
        try:
            if not self.network:
                logger.error("[Werewolf] No network!")
                return
            
            # Human player: show in channel as private message
            if not agent_id.startswith("ai_player_"):
                await self._broadcast(f"🔒 **[私信]** {text}")
                return
            
            event = Event(
                event_name="thread.direct_message.send",
                source_id="werewolf_host",
                destination_id=agent_id,
                payload={
                    "content": {"text": text},
                    "sender_name": "🎮 主持人"
                },
                visibility=EventVisibility.DIRECT
            )
            logger.info(f"[Werewolf] Sending DM Event to {agent_id} via send_event()")
            await self.send_event(event)
            logger.info(f"[Werewolf] 📨 -> {agent_id}: {text[:30]}... (Sent)")
        except Exception as e:
            logger.error(f"[Werewolf] Error in _send_dm to {agent_id}: {e}", exc_info=True)

    def _set_timer(self, name: str, seconds: int, callback):
        self._cancel_timer(name)
        
        async def timer_task():
            await asyncio.sleep(seconds)
            await callback()
        
        self.timers[name] = asyncio.create_task(timer_task())
        logger.info(f"[Werewolf] ⏰ Timer {name}={seconds}s")

    def _cancel_timer(self, name: str):
        if name in self.timers:
            self.timers[name].cancel()
            del self.timers[name]
