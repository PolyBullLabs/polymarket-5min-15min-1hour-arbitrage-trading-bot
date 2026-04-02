"""
Entry point for running scripts as modules
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import and run setup
if __name__ == '__main__':
    from src.scripts.setup.setup import main
    main()

