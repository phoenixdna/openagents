import sys
import os
import argparse
from pathlib import Path

# Add src to python path to prioritize Local Source Code
current_dir = Path(__file__).parent.absolute()
src_dir = current_dir.parent.parent / "src"
sys.path.insert(0, str(src_dir))

print(f"DEBUG: Added {src_dir} to sys.path")
print(f"DEBUG: Running network with python: {sys.executable}")

# Import after path modification
try:
    from openagents.cli import app
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import openagents.cli: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

if __name__ == "__main__":
    # Simulate CLI arguments: "network run network.yaml"
    # We need to pass these to the typer app or call the command directly.
    # Typer apps usually take sys.argv.
    
    # We construct the arguments manually to ensure correct execution
    sys.argv = ["openagents", "network", "start", "network.yaml"]
    
    print("Starting Network...")
    try:
        app()
    except SystemExit as e:
        if e.code != 0:
            print(f"Network exited with code {e.code}")
    except Exception as e:
        print(f"Network crashed: {e}")
        import traceback
        traceback.print_exc()
