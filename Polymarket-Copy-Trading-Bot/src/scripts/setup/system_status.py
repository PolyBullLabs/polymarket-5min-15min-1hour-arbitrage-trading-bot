#!/usr/bin/env python3
"""
System status check script

Verify all system components and configuration
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.system_status import run_system_status_check

if __name__ == '__main__':
    asyncio.run(run_system_status_check())

