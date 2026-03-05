import sys
from pathlib import Path

# Add apps/api directory to Python path so tests can import main
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
