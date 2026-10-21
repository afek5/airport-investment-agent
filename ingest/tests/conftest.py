import sys
from pathlib import Path

INGEST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INGEST))
