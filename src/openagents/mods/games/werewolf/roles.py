"""
Role definitions for Werewolf Game.
"""

from enum import Enum


class Team(Enum):
    """Game teams."""
    WEREWOLF = "werewolf"
    VILLAGER = "villager"


class RoleType(Enum):
    """Player roles in the game."""
    WEREWOLF = "werewolf"   # 狼人
    VILLAGER = "villager"   # 村民
    SEER = "seer"           # 预言家
    WITCH = "witch"         # 女巫
    
    @property
    def team(self) -> Team:
        """Get the team this role belongs to."""
        if self == RoleType.WEREWOLF:
            return Team.WEREWOLF
        return Team.VILLAGER
    
    @property
    def chinese_name(self) -> str:
        """Get Chinese name for the role."""
        names = {
            RoleType.WEREWOLF: "狼人",
            RoleType.VILLAGER: "村民",
            RoleType.SEER: "预言家",
            RoleType.WITCH: "女巫",
        }
        return names.get(self, "未知")


class Role:
    """A player's role in the game."""
    
    def __init__(self, role_type: RoleType):
        self.role_type = role_type
        self.team = role_type.team
    
    def __repr__(self):
        return f"Role({self.role_type.chinese_name})"
