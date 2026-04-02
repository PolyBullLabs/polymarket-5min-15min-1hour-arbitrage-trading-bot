"""
Entry point for running utils modules
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    # When run as python -m src.utils.system_status, execute system status check
    try:
        from src.utils.system_status import run_system_status_check
        asyncio.run(run_system_status_check())
    except ImportError as e:
        print(f"Error importing system_status: {e}")
        print("Usage: python -m src.utils.system_status")
        sys.exit(1)

