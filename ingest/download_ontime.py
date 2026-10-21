"""Download BTS Reporting Carrier On-Time Performance, Sep 2025 -> Aug 2026.

One zip per month in data/raw/ontime/ (about 4 min per month via the
TranStats POST). Months already present are skipped; Aug 2026 is copied
from the existing raw sample. Run detached:

    nohup uv run python ingest/download_ontime.py > data/raw/ontime/download.log 2>&1 &
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transtats import ONTIME_REPORTING, download_months, months_between

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "ontime"

FIELDS = [
    "FL_DATE", "OP_UNIQUE_CARRIER", "ORIGIN", "DEST", "DEP_DELAY", "DEP_DEL15",
    "TAXI_OUT", "TAXI_IN", "ARR_DELAY", "ARR_DEL15", "CANCELLED", "DIVERTED",
    "DISTANCE", "CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY", "LATE_AIRCRAFT_DELAY",
]
REQUIRED = ["FL_DATE", "ORIGIN", "DEP_DEL15", "TAXI_OUT", "CANCELLED", "NAS_DELAY", "DEP_DELAY"]

if __name__ == "__main__":
    months = months_between((2025, 9), (2026, 8))
    # newest first, so the most useful months land early
    months.reverse()
    existing = {(2026, 8): ROOT / "data" / "raw" / "ontime_2026_08.zip"}
    download_months(ONTIME_REPORTING, months, FIELDS, DEST, "ontime", REQUIRED, existing)
