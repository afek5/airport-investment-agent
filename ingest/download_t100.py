"""Download BTS T-100 Segment (All Carriers) months into data/raw/t100/.

DEST_COUNTRY and ORIGIN_COUNTRY are requested explicitly: the form drops
unrequested fields silently (the old Jul 2026 raw sample lacks them).

    uv run python ingest/download_t100.py 2025-08 2026-07          # primary 12 months
    nohup uv run python ingest/download_t100.py 2024-08 2025-07 \
        > data/raw/t100/download.log 2>&1 &                        # prior 12 months
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transtats import T100_SEGMENT_ALL, download_months, months_between  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "t100"

FIELDS = [
    "DEPARTURES_SCHEDULED", "DEPARTURES_PERFORMED", "SEATS", "PASSENGERS", "FREIGHT",
    "DISTANCE", "CARRIER", "ORIGIN", "ORIGIN_STATE_ABR", "ORIGIN_COUNTRY",
    "DEST", "DEST_STATE_ABR", "DEST_COUNTRY", "AIRCRAFT_CONFIG", "CLASS", "YEAR", "MONTH",
]
REQUIRED = [
    "DEPARTURES_SCHEDULED", "DEPARTURES_PERFORMED", "SEATS", "PASSENGERS", "FREIGHT",
    "DISTANCE", "ORIGIN", "ORIGIN_COUNTRY", "DEST", "DEST_COUNTRY", "CLASS", "YEAR", "MONTH",
]


def _ym(s: str) -> tuple[int, int]:
    y, m = s.split("-")
    return int(y), int(m)


if __name__ == "__main__":
    start, end = (_ym(sys.argv[1]), _ym(sys.argv[2])) if len(sys.argv) == 3 else ((2025, 8), (2026, 7))
    months = list(reversed(months_between(start, end)))
    download_months(T100_SEGMENT_ALL, months, FIELDS, DEST, "t100", REQUIRED)
