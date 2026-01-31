"""
AI Prompts for Werewolf Game.

These prompts are used by AI players to respond to the Host.
Since all game logic is now in the Host, these prompts focus on
helping AI generate appropriate responses.
"""

from typing import List, Optional


def get_role_prompt(role: str) -> str:
    """Get the base prompt for a role."""
    prompts = {
        "wolf": """你是一名狼人。你的目标是：
1. 在夜晚与队友商议击杀目标
2. 白天混入好人阵营，避免暴露身份
3. 当被问到时，回复简短直接的行动指令

夜晚击杀回复格式：杀 [玩家名]
白天发言：要表现得像好人，可以适当引导方向""",

        "villager": """你是一名村民。你的目标是：
1. 白天通过发言和投票找出狼人
2. 观察其他玩家的发言寻找破绽
3. 保护好人阵营

白天发言：分析局势，表达自己的判断
投票回复格式：投票 [玩家名]""",

        "seer": """你是预言家。你的目标是：
1. 每晚查验一名玩家的身份
2. 白天巧妙地传递查验信息
3. 帮助好人阵营找出狼人

夜晚查验回复格式：查验 [玩家名]
白天发言：可以适当暗示查验结果，但要小心暴露自己""",

        "witch": """你是女巫。你有两瓶药：
- 解药：可以救被狼人杀的人
- 毒药：可以毒杀任意一人

夜晚回复格式：
- 救人：救
- 不救：不救
- 毒人：毒 [玩家名]
- 不使用：不使用"""
    }
    return prompts.get(role, "你是一名玩家，根据游戏情况做出合理的决策。")


def build_action_prompt(role: str, phase: str, context: dict) -> str:
    """Build a prompt for AI to respond with an action."""
    
    if phase == "wolf_kill":
        targets = context.get("targets", [])
        return f"🐺 选择击杀目标。可选: {', '.join(targets)}\n回复格式: 杀 [玩家名]"
    
    if phase == "witch_save":
        victim = context.get("victim", "")
        return f"💊 {victim}被袭击了。回复「救」使用解药，或「不救」放弃。"
    
    if phase == "witch_poison":
        targets = context.get("targets", [])
        return f"☠️ 是否使用毒药？可选: {', '.join(targets)}\n回复「毒 [玩家名]」或「不使用」"
    
    if phase == "seer_check":
        targets = context.get("targets", [])
        return f"🔮 选择查验目标。可选: {', '.join(targets)}\n回复格式: 查验 [玩家名]"
    
    if phase == "speech":
        return "🎤 轮到你发言。请简短表达你的看法（上限240字）。"
    
    if phase == "vote":
        targets = context.get("targets", [])
        return f"🗳️ 投票时间。可选: {', '.join(targets)}\n回复格式: 投票 [玩家名]"
    
    return "请根据当前游戏情况做出回复。"


def get_system_prompt(role: str, player_name: str, teammates: List[str] = None) -> str:
    """Get the system prompt for an AI player."""
    base = f"你是 {player_name}，在一局6人狼人杀游戏中扮演{get_role_chinese(role)}。\n\n"
    base += get_role_prompt(role)
    
    if role == "wolf" and teammates:
        base += f"\n\n你的狼人队友是: {', '.join(teammates)}"
    
    base += "\n\n重要规则：\n"
    base += "- 回复要简短直接\n"
    base += "- 遵循指定的回复格式\n"
    base += "- 不要暴露自己的角色\n"
    
    return base


def get_role_chinese(role: str) -> str:
    """Get Chinese name of role."""
    names = {
        "wolf": "狼人",
        "villager": "村民",
        "seer": "预言家",
        "witch": "女巫"
    }
    return names.get(role, role)
