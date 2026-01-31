"""
Simplified Game State for Werewolf.

This module provides basic data structures for the game.
(Most logic is now in mod.py's Host)
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


class RoleType(Enum):
    """Player roles."""
    WEREWOLF = "wolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"
    
    @property
    def chinese_name(self) -> str:
        names = {
            "wolf": "狼人",
            "villager": "村民",
            "seer": "预言家",
            "witch": "女巫"
        }
        return names.get(self.value, self.value)
    
    @property
    def is_wolf(self) -> bool:
        return self == RoleType.WEREWOLF


class Team(Enum):
    """Teams in the game."""
    WEREWOLF = "werewolf"
    VILLAGER = "villager"


# Legacy compatibility - keep for imports
class GamePhase(Enum):
    """Game phases (legacy - use mod.py's GamePhase instead)."""
    WAITING = auto()
    NIGHT = auto()
    DAY_DISCUSSION = auto()
    DAY_VOTING = auto()
    GAME_OVER = auto()


@dataclass 
class Player:
    """Simple player data."""
    name: str
    agent_id: str
    role: RoleType = RoleType.VILLAGER
    alive: bool = True
    number: int = 0


def get_role_list(player_count: int = 6) -> List[RoleType]:
    """Get role distribution for given player count."""
    # Standard 6-player setup
    return [
        RoleType.WEREWOLF,
        RoleType.WEREWOLF,
        RoleType.VILLAGER,
        RoleType.VILLAGER,
        RoleType.SEER,
        RoleType.WITCH
    ]
