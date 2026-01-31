"""
Werewolf Game Adapter - Placeholder.

Since Werewolf is a network-level mod that doesn't require agent-level adapters,
this file provides a minimal adapter that does nothing.
"""

from openagents.core.base_mod_adapter import BaseModAdapter


class WerewolfAdapter(BaseModAdapter):
    """Placeholder adapter for Werewolf mod (not used)."""
    
    def __init__(self):
        super().__init__(mod_name="werewolf")
    
    def initialize(self) -> bool:
        return True
    
    def shutdown(self) -> bool:
        return True
    
    def get_tools(self):
        return []
    
    async def process_incoming_mod_message(self, message) -> None:
        pass
