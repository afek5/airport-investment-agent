"""A small hand-made Snapshot with every SPEC §3 table, designed so the percentiles are exact.

Six Primary Airports (plus one non-primary that must be ignored):

| airport | LF (class F) | On-Time (12 mo)        | TAF FY24→FY35 | CY24→CY25         | CBSA pop |
|---------|--------------|------------------------|---------------|-------------------|----------|
| BOS MA  | 70 % → p20   | 2,400 flts, 25 %, 20 m | ×1.2 → p40    | 20.0M→21.0M → p60 | 4.9M p100|
| BDL CT  | 75 % → p40   | 2,400 flts, 15 %, 14 m | ×1.5 → p100   | 3.0M→3.3M → p100  | 1.2M p60 |
| MHT NH  | 80 % → p60   | 2,400 flts, 10 %, 12 m | ×1.1 → p20    | 1.0M→0.98M → p20  | 0.43M p20|
| PWM ME  | 85 % → p80   | 900 flts (too thin)    | ×1.4 → p80    | 1.2M→1.284M → p80 | 0.56M p40|
| SFO CA  | 90 % → p100  | 2,400 flts, 30 %, 22 m | ×1.3 → p60    | 25.0M→25.5M → p40 | 4.6M p80 |
| BTV VT  | no T-100     | 1,200 flts, 20 %, 16 m | no TAF        | none→0.6M         | no CBSA  |

So PWM has Capacity Pressure 80/missing/missing → 62 (Provisional, 5/7), and BTV has no
measured Demand Momentum metric → not ranked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app import snapshot

REAL_SNAPSHOT = snapshot.ROOT / "data" / "snapshot"

AIRPORTS = pd.DataFrame([
    ("BOS", "BOS", "KBOS", "Boston Logan International", "Boston", "MA", "NE", "L", True, 42.36, -71.0, "14460", "Boston", 6),
    ("BDL", "BDL", "KBDL", "Bradley International", "Windsor Locks", "CT", "NE", "M", True, 41.9, -72.7, "25540", "Hartford", 3),
    ("MHT", "MHT", "KMHT", "Manchester-Boston Regional", "Manchester", "NH", "NE", "S", True, 42.9, -71.4, "31700", "Manchester", 2),
    ("PWM", "PWM", "KPWM", "Portland International Jetport", "Portland", "ME", "NE", "S", True, 43.6, -70.3, "38860", "Portland", 2),
    ("SFO", "SFO", "KSFO", "San Francisco International", "San Francisco", "CA", "WP", "L", True, 37.6, -122.4, "41860", "SF", 4),
    ("BTV", "BTV", "KBTV", "Burlington International", "Burlington", "VT", "NE", "N", True, 44.5, -73.2, None, None, 3),
    ("XYZ", "XYZ", "KXYZ", "Not Primary Field", "Nowhere", "MA", "NE", "N", False, 42.0, -71.5, "14460", "Boston", 1),
], columns=["iata", "faa_locid", "icao", "name", "city", "state", "faa_region", "hub_size", "is_primary",
            "lat", "lon", "cbsa_code", "cbsa_name", "runway_count"])

LF = {"BOS": 0.70, "BDL": 0.75, "MHT": 0.80, "PWM": 0.85, "SFO": 0.90, "XYZ": 0.99}
ONTIME = {  # flights per month, dep_del15_share (fraction), avg taxi-out
    "BOS": (200, 0.25, 20.0), "BDL": (200, 0.15, 14.0), "MHT": (200, 0.10, 12.0),
    "PWM": (75, 0.40, 30.0), "SFO": (200, 0.30, 22.0), "BTV": (100, 0.20, 16.0), "XYZ": (500, 0.9, 40.0),
}
TAF = {"BOS": 1.2, "BDL": 1.5, "MHT": 1.1, "PWM": 1.4, "SFO": 1.3}
ENPL = {"BOS": (20.0e6, 21.0e6), "BDL": (3.0e6, 3.3e6), "MHT": (1.0e6, 0.98e6), "PWM": (1.2e6, 1.284e6),
        "SFO": (25.0e6, 25.5e6), "BTV": (None, 0.6e6)}
POP = {"14460": 4.9e6, "25540": 1.2e6, "31700": 0.43e6, "38860": 0.56e6, "41860": 4.6e6}

T100_MONTHS = [(2024, m) for m in range(8, 13)] + [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 8)]
ONTIME_MONTHS = [(2025, m) for m in range(9, 13)] + [(2026, m) for m in range(1, 9)]


def build_t100() -> pd.DataFrame:
    rows = []
    for y, m in T100_MONTHS:
        recent = (y, m) >= (2025, 8)
        for iata, lf in LF.items():
            pax = round(lf * 1000) if recent else round((lf - 0.05) * 1000)  # passengers grew ~5-7 %
            rows.append((y, m, iata, "US", "ZZZ", "US", "F", 1000, 10, 10, 1000, pax, 0))
            # a cargo row with seats: Load Factor must ignore it (class F only)
            rows.append((y, m, iata, "US", "ANC", "US", "G", 3200, 5, 5, 500, 0, 90_000))
    return pd.DataFrame(rows, columns=["year", "month", "origin", "origin_country", "dest", "dest_country",
                                       "service_class", "distance_mi", "departures_performed",
                                       "departures_scheduled", "seats", "passengers", "freight_lbs"])


def build_ontime() -> pd.DataFrame:
    rows = []
    for y, m in ONTIME_MONTHS:
        for iata, (n, d15, taxi) in ONTIME.items():
            rows.append((iata, y, m, n, d15, taxi, 0.01, 2.0 if iata != "SFO" else 6.0, 12.0))
    # an older month outside the 12-month window that would swamp BOS if it were counted
    rows.append(("BOS", 2025, 8, 100_000, 0.95, 60.0, 0.5, 30.0, 90.0))
    return pd.DataFrame(rows, columns=["origin", "year", "month", "flights", "dep_del15_share", "avg_taxi_out_min",
                                       "cancel_rate", "nas_delay_min_per_flight", "avg_dep_delay_min"])


def build_taf() -> pd.DataFrame:
    rows = []
    for iata, ratio in TAF.items():
        base = 24_765_642 if iata == "SFO" else 1_000_000
        intl = 7_275_124 if iata == "SFO" else 0  # SFO FY2024: 24,765,642 total − 17,490,518 domestic
        for fy, total, ops in ((2024, base, 350_805), (2030, round(base * 1.15), 400_000),
                               (2035, round(base * ratio), 450_000)):
            # international grows faster than total for SFO, so a domestic-only CAGR would differ
            intl_fy = round(intl * (1 + (fy - 2024) * 0.05))
            rows.append((iata, fy, fy > 2024, total, intl_fy, ops, ops + 1000))
    return pd.DataFrame(rows, columns=["iata", "fiscal_year", "is_forecast", "enplanements_total",
                                       "enplanements_international", "ops_air_carrier", "ops_itinerant_total"])


def build_enplanements() -> pd.DataFrame:
    rows = [(i, a, b, None if a is None else round(100 * (b / a - 1), 2)) for i, (a, b) in ENPL.items()]
    return pd.DataFrame(rows, columns=["iata", "cy2024", "cy2025", "yoy_pct"])


def build_metro() -> pd.DataFrame:
    rows = [(c, f"CBSA {c}", *(int(p * (0.95 + 0.01 * k)) for k in range(5)), int(p)) for c, p in POP.items()]
    return pd.DataFrame(rows, columns=["cbsa_code", "cbsa_name", "pop_2020", "pop_2021", "pop_2022", "pop_2023",
                                       "pop_2024", "pop_2025"])


def build_runway_capacity() -> pd.DataFrame:
    return pd.DataFrame([("SFO", 60, 30, 60, 30, "fixture row, not real")],
                        columns=["iata", "vfr_arrivals_hr", "ifr_arrivals_hr", "vfr_departures_hr",
                                 "ifr_departures_hr", "source_note"])


def write_snapshot(path: Path, tables: dict[str, pd.DataFrame]) -> None:
    for name, df in tables.items():
        df.to_parquet(path / f"{name}.parquet", index=False)
    meta = {name: {"source": f"fixture {name}", "url": f"https://example.test/{name}", "as_of": "fixture",
                   "rows": len(df), "window": "fixture"} for name, df in tables.items()}
    (path / "manifest.json").write_text(json.dumps({"tables": meta}))


def all_tables() -> dict[str, pd.DataFrame]:
    return {
        "airports": AIRPORTS, "t100_routes": build_t100(), "ontime_airport_month": build_ontime(),
        "taf": build_taf(), "enplanements": build_enplanements(), "metro_population": build_metro(),
        "runway_capacity": build_runway_capacity(),
    }


@pytest.fixture
def scoring_snapshot(tmp_path: Path):
    write_snapshot(tmp_path, all_tables())
    snapshot.use_snapshot_dir(tmp_path)
    yield tmp_path
    snapshot.use_snapshot_dir(REAL_SNAPSHOT)


def require_real(*tables: str):
    missing = [t for t in tables if not (REAL_SNAPSHOT / f"{t}.parquet").exists()]
    if missing:
        pytest.skip(f"real Snapshot lacks {missing} (P1-A builds them)")
    snapshot.use_snapshot_dir(REAL_SNAPSHOT)
