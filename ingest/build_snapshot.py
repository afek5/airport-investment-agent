"""Build the Snapshot: data/snapshot/*.parquet + data/snapshot/manifest.json.

    make snapshot      # == uv run --project backend python ingest/build_snapshot.py

Each table builder reads raw public downloads from data/raw/ (see
docs/research/data-sources.md), writes one Parquet file, and returns a
manifest entry. Coverage checks fail loudly (SnapshotError) when a table
misses its window or a required column (SPEC §3).

P0 builds `airports` and `t100_routes`. P1-A adds the remaining SPEC §3
tables by registering more builders in TABLES.
"""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "snapshot"

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# T-100 window: the required 12 months, plus any prior months present (P1-A extends to 24).
T100_REQUIRED = ((2025, 8), (2026, 7))
T100_MIN_MONTH = (2024, 8)


class SnapshotError(RuntimeError):
    """A table missed its window or a required column. Never swallowed."""


def ym_label(y: int, m: int) -> str:
    return f"{MONTH_ABBR[m - 1]} {y}"


def months_between(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    y, m = start
    out = []
    while (y, m) <= end:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def require_columns(df: pd.DataFrame, cols: list[str], table: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SnapshotError(f"{table}: missing required columns {missing}")


def window_entry(months: list[tuple[int, int]]) -> dict:
    months = sorted(months)
    return {
        "months": [f"{y}-{m:02d}" for y, m in months],
        "window": f"{len(months)} months, {ym_label(*months[0])}–{ym_label(*months[-1])}",
        "as_of": ym_label(*months[-1]),
    }


# ───────────────────────────── airports ─────────────────────────────

FAA_XLSX = RAW / "faa_cy2025_commercial_enplanements.xlsx"
FAA_URL = ("https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/"
           "arp-cy2025-commercial-service-enplanements.xlsx")
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"
CBSA_CSV = RAW / "cbsa2025.csv"
CBSA_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/cbsa-est2025-alldata.csv"
US_COUNTRIES = {"US", "PR", "GU", "VI", "AS", "MP"}

# Hand-map fallback for the golden airports (SPEC §3). P1-A adds the Census Geocoder for the rest.
CBSA_HAND_MAP = {
    "ANC": "11260", "LAX": "31080", "SNA": "31080", "SFO": "41860", "BOS": "14460",
    "BDL": "25540", "PVD": "39300", "MHT": "31700", "PWM": "38860", "BTV": "15540",
}

AIRPORT_COLUMNS = ["iata", "faa_locid", "icao", "name", "city", "state", "faa_region", "hub_size",
                   "is_primary", "lat", "lon", "cbsa_code", "cbsa_name", "runway_count"]


def read_faa_enplanements() -> pd.DataFrame:
    if not FAA_XLSX.exists():
        raise SnapshotError(f"airports: raw file missing: {FAA_XLSX}")
    df = pd.read_excel(FAA_XLSX, dtype={"Locid": str})
    require_columns(df, ["RO", "ST", "Locid", "City", "Airport Name", "S/L", "Hub",
                         "CY 25 Enplanements", "CY 24 Enplanements"], "airports(faa xlsx)")
    df = df[df["S/L"].notna() & df["Locid"].notna()].copy()
    df["Locid"] = df["Locid"].astype(str).str.strip()
    return df


def build_airports() -> dict:
    faa = read_faa_enplanements()
    faa = faa[faa["S/L"].astype(str).str.strip() == "P"].copy()

    oa = pd.read_csv(RAW / "airports.csv", dtype=str, keep_default_na=False)
    oa = oa[oa["iso_country"].isin(US_COUNTRIES) & (oa["type"] != "closed")]
    type_rank = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}
    oa = oa.assign(_rank=oa["type"].map(type_rank).fillna(9))

    rw = pd.read_csv(RAW / "runways.csv", dtype=str, keep_default_na=False)
    rw = rw[(rw["closed"] != "1") & ~rw["le_ident"].str.upper().str.startswith("H")]
    rw_len = pd.to_numeric(rw["length_ft"], errors="coerce").fillna(0)
    runway_counts = rw[rw_len >= 1000].groupby("airport_ident").size()

    def match(locid: str) -> pd.Series | None:
        for col, key in (("local_code", locid), ("iata_code", locid), ("gps_code", "K" + locid)):
            hit = oa[oa[col] == key]
            if len(hit):
                return hit.sort_values("_rank").iloc[0]
        return None

    cbsa = pd.read_csv(CBSA_CSV, dtype=str, encoding="latin-1")
    cbsa = cbsa[cbsa["LSAD"].isin(["Metropolitan Statistical Area", "Micropolitan Statistical Area"])]
    cbsa_names = dict(zip(cbsa["CBSA"], cbsa["NAME"]))

    rows = []
    for _, r in faa.iterrows():
        locid = r["Locid"]
        o = match(locid)
        iata = (o["iata_code"] if o is not None and o["iata_code"] else locid)
        cbsa_code = CBSA_HAND_MAP.get(iata)
        rows.append({
            "iata": iata,
            "faa_locid": locid,
            "icao": (o["icao_code"] or o["gps_code"]) if o is not None else None,
            "name": str(r["Airport Name"]).strip(),
            "city": str(r["City"]).strip(),
            "state": str(r["ST"]).strip(),
            "faa_region": str(r["RO"]).strip(),
            "hub_size": (str(r["Hub"]).strip() if pd.notna(r["Hub"]) else "N"),
            "is_primary": True,
            "lat": float(o["latitude_deg"]) if o is not None else None,
            "lon": float(o["longitude_deg"]) if o is not None else None,
            "cbsa_code": cbsa_code,
            "cbsa_name": cbsa_names.get(cbsa_code) if cbsa_code else None,
            "runway_count": int(runway_counts.get(o["ident"], 0)) if o is not None else None,
        })
    df = pd.DataFrame(rows, columns=AIRPORT_COLUMNS)
    if df["iata"].duplicated().any():
        raise SnapshotError(f"airports: duplicate iata {df[df['iata'].duplicated()]['iata'].tolist()}")
    if len(df) < 370:
        raise SnapshotError(f"airports: only {len(df)} primary airports (expected ≥ 370)")
    unmatched = df[df["lat"].isna()]["iata"].tolist()
    df = df.sort_values("iata").reset_index(drop=True)
    df.to_parquet(OUT / "airports.parquet", index=False)
    return {
        "source": "FAA CY2025 commercial-service enplanements (universe: S/L = P) + OurAirports airports/runways"
                  " + Census PEP CBSA names (hand-mapped CBSA for golden airports)",
        "url": [FAA_URL, OURAIRPORTS_URL, RUNWAYS_URL, CBSA_URL],
        "as_of": "CY2025",
        "window": "current",
        "rows": len(df),
        "notes": [f"{len(unmatched)} airports without an OurAirports match: {unmatched}"] if unmatched else [],
    }


# ───────────────────────────── t100_routes ─────────────────────────────

T100_URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45"
T100_RAW_COLS = ["YEAR", "MONTH", "ORIGIN", "ORIGIN_COUNTRY", "DEST", "DEST_COUNTRY", "CLASS", "DISTANCE",
                 "DEPARTURES_PERFORMED", "DEPARTURES_SCHEDULED", "SEATS", "PASSENGERS", "FREIGHT"]
T100_COLUMNS = ["year", "month", "origin", "origin_country", "dest", "dest_country", "service_class",
                "distance_mi", "departures_performed", "departures_scheduled", "seats", "passengers", "freight_lbs"]


def read_t100_month(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        df = pd.read_csv(z.open(name), dtype={"ORIGIN": str, "DEST": str, "CLASS": str,
                                              "ORIGIN_COUNTRY": str, "DEST_COUNTRY": str},
                         keep_default_na=False, na_values=[""])
    require_columns(df, T100_RAW_COLS, f"t100_routes({path.name})")
    return df[T100_RAW_COLS]


def build_t100_routes() -> dict:
    files = sorted((RAW / "t100").glob("t100_*.zip"))
    frames, months = [], []
    for f in files:
        y, m = int(f.stem.split("_")[1]), int(f.stem.split("_")[2])
        if (y, m) < T100_MIN_MONTH or (y, m) > T100_REQUIRED[1]:
            continue
        frames.append(read_t100_month(f))
        months.append((y, m))
    missing = [ym for ym in months_between(*T100_REQUIRED) if ym not in months]
    if missing:
        raise SnapshotError(f"t100_routes: missing required months {[f'{y}-{m:02d}' for y, m in missing]}")
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["DEPARTURES_PERFORMED"] > 0]
    agg = (raw.groupby(["YEAR", "MONTH", "ORIGIN", "ORIGIN_COUNTRY", "DEST", "DEST_COUNTRY", "CLASS"],
                       as_index=False, dropna=False)
           .agg(DISTANCE=("DISTANCE", "max"),
                DEPARTURES_PERFORMED=("DEPARTURES_PERFORMED", "sum"),
                DEPARTURES_SCHEDULED=("DEPARTURES_SCHEDULED", "sum"),
                SEATS=("SEATS", "sum"), PASSENGERS=("PASSENGERS", "sum"), FREIGHT=("FREIGHT", "sum")))
    agg.columns = T100_COLUMNS[:7] + T100_COLUMNS[7:]
    agg = agg[T100_COLUMNS]
    for c in ["year", "month"]:
        agg[c] = agg[c].astype("int32")
    for c in ["distance_mi", "departures_performed", "departures_scheduled", "seats", "passengers", "freight_lbs"]:
        agg[c] = agg[c].round().astype("int64")
    agg = agg.sort_values(["year", "month", "origin", "dest", "service_class"]).reset_index(drop=True)
    agg.to_parquet(OUT / "t100_routes.parquet", index=False, compression="zstd")
    entry = {
        "source": "BTS TranStats T-100 Segment (All Carriers), carrier and aircraft aggregated away",
        "url": T100_URL,
        "rows": len(agg),
        **window_entry(months),
    }
    return entry


# ───────────────────────────── driver ─────────────────────────────

TABLES = {
    "airports": build_airports,
    "t100_routes": build_t100_routes,
}


def main(only: list[str] | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"tables": {}}
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, fn in TABLES.items():
        if only and name not in only:
            continue
        print(f"building {name} …", flush=True)
        entry = fn()
        entry["built_at"] = built_at
        manifest["tables"][name] = entry
        print(f"  {name}: {entry['rows']} rows, {entry.get('window', '')}", flush=True)
    manifest["built_at"] = built_at
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    try:
        main(sys.argv[1:] or None)
    except SnapshotError as e:
        print(f"SNAPSHOT FAILED: {e}", file=sys.stderr)
        sys.exit(1)
