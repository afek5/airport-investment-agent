"""Shared fixtures: a tiny hand-made Snapshot for exact maths, and the real Snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app import snapshot

REAL_SNAPSHOT = snapshot.ROOT / "data" / "snapshot"

AIRPORTS = pd.DataFrame([
    # iata, faa_locid, icao, name, city, state, faa_region, hub_size, is_primary, lat, lon, cbsa_code, cbsa_name, runway_count
    ("AAA", "AAA", "KAAA", "Alpha International", "Alphaville", "AK", "AL", "M", True, 61.0, -150.0, None, None, 3),
    ("LAX", "LAX", "KLAX", "Los Angeles International", "Los Angeles", "CA", "WP", "L", True, 33.9, -118.4, "31080", "LA", 4),
    ("SNA", "SNA", "KSNA", "John Wayne/Orange County", "Santa Ana", "CA", "WP", "M", True, 33.7, -117.9, "31080", "LA", 2),
    ("BUR", "BUR", "KBUR", "Hollywood Burbank", "Burbank", "CA", "WP", "M", True, 34.2, -118.4, "31080", "LA", 2),
    ("SFO", "SFO", "KSFO", "San Francisco International", "San Francisco", "CA", "WP", "L", True, 37.6, -122.4, "41860", "SF", 4),
], columns=["iata", "faa_locid", "icao", "name", "city", "state", "faa_region", "hub_size", "is_primary",
            "lat", "lon", "cbsa_code", "cbsa_name", "runway_count"])

T100_COLS = ["year", "month", "origin", "origin_country", "dest", "dest_country", "service_class", "distance_mi",
             "departures_performed", "departures_scheduled", "seats", "passengers", "freight_lbs"]


def t100_rows() -> pd.DataFrame:
    """AAA over 12 months (Aug 2025–Jul 2026) plus one older month that must be ignored.

    Per month from AAA:
      F  → SEA   1,400 mi   9 deps, 900 pax
      F  → ORD   2,999 mi   1 dep,  100 pax   (just under the threshold)
      F  → ATL   3,000 mi   1 dep,  300 pax   (exactly on the threshold: counts)
      G  → NRT   3,500 mi  10 deps, 0 pax, 1,000,000 lbs
    """
    rows = []
    months = [(2025, m) for m in range(8, 13)] + [(2026, m) for m in range(1, 8)]
    for y, m in months:
        rows += [
            (y, m, "AAA", "US", "SEA", "US", "F", 1400, 9, 9, 1200, 900, 0),
            (y, m, "AAA", "US", "ORD", "US", "F", 2999, 1, 1, 150, 100, 0),
            (y, m, "AAA", "US", "ATL", "US", "F", 3000, 1, 1, 320, 300, 0),
            (y, m, "AAA", "US", "NRT", "JP", "G", 3500, 10, 10, 0, 0, 1_000_000),
        ]
    # an older month outside the last-12 window: would change every share if counted
    rows.append((2025, 7, "AAA", "US", "ATL", "US", "F", 3000, 500, 500, 50000, 40000, 0))
    return pd.DataFrame(rows, columns=T100_COLS)


@pytest.fixture
def fixture_snapshot(tmp_path: Path):
    AIRPORTS.to_parquet(tmp_path / "airports.parquet", index=False)
    t100_rows().to_parquet(tmp_path / "t100_routes.parquet", index=False)
    (tmp_path / "manifest.json").write_text(json.dumps({"tables": {
        "airports": {"as_of": "CY2025", "rows": len(AIRPORTS), "window": "current"},
        "t100_routes": {"as_of": "Jul 2026", "rows": 49, "window": "13 months, Jul 2025–Jul 2026"},
    }}))
    snapshot.use_snapshot_dir(tmp_path)
    yield tmp_path
    snapshot.use_snapshot_dir(REAL_SNAPSHOT)


@pytest.fixture
def real_snapshot():
    if not (REAL_SNAPSHOT / "t100_routes.parquet").exists():
        pytest.skip("real Snapshot not built (make snapshot)")
    snapshot.use_snapshot_dir(REAL_SNAPSHOT)
    yield REAL_SNAPSHOT
