"""
Werewolf Game Mod for OpenAgents.

A 6-player Werewolf (Mafia) game where:
- Host manages all game logic (hardcoded, deterministic)
- All communication flows through the Host
- AI players respond to Host prompts
- Human player interacts via channel messages
"""

from .mod import WerewolfNetworkMod
from .game_state import RoleType, Team, Player

__all__ = [
    "WerewolfNetworkMod",
    "RoleType",
    "Team",
    "Player",
]

# Module version
__version__ = "2.0.0"
