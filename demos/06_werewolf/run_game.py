#!/usr/bin/env python3
"""
Standalone Werewolf Game Launcher

This script bypasses the openagents CLI entirely and directly launches
the network using the local source code.

Usage:
    python run_game.py
"""

import sys
import os
from pathlib import Path

# =====================================================
# CRITICAL: Force use of LOCAL SOURCE CODE
# =====================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # demos/06_werewolf -> project root
SRC_DIR = PROJECT_ROOT / "src"

# Insert at position 0 to override any installed packages
sys.path.insert(0, str(SRC_DIR))

print("=" * 60)
print("🚀 STANDALONE WEREWOLF GAME LAUNCHER")
print("=" * 60)
print(f"📁 Using local source: {SRC_DIR}")
print(f"🐍 Python interpreter: {sys.executable}")
print("=" * 60)

# Change to the demo directory so relative paths in config work
os.chdir(SCRIPT_DIR)

# =====================================================
# Import and Launch
# =====================================================
try:
    from openagents.launchers.network_launcher import launch_network
    print("✅ Successfully imported from local source!")
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import openagents: {e}")
    print(f"   sys.path[0] = {sys.path[0]}")
    sys.exit(1)

# Additional verification - check that we're using the modified mod
try:
    from openagents.mods.games.werewolf.mod import WerewolfNetworkMod
    # Check for our unique debug attribute/method
    print("✅ Werewolf mod imported successfully!")
except ImportError as e:
    print(f"⚠️ Warning: Could not verify werewolf mod: {e}")

if __name__ == "__main__":
    CONFIG_FILE = "network.yaml"
    
    if not Path(CONFIG_FILE).exists():
        print(f"❌ ERROR: {CONFIG_FILE} not found in {SCRIPT_DIR}")
        sys.exit(1)
    
    print(f"\n🎮 Launching network with config: {CONFIG_FILE}\n")
    
    try:
        launch_network(
            config_path=CONFIG_FILE,
            runtime=None,  # Run indefinitely
            workspace_path=str(SCRIPT_DIR)
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Game stopped by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
