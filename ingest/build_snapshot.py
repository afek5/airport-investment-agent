"""Build the Snapshot: data/snapshot/*.parquet + data/snapshot/manifest.json.

    make snapshot                          # every table (== uv run --project backend python ingest/build_snapshot.py)
    uv run --project backend python ingest/build_snapshot.py taf   # one table, merged into the manifest

Each table builder reads raw public downloads from data/raw/ (see
docs/research/data-sources.md), writes one Parquet file, and returns a
manifest entry. Coverage checks fail loudly (SnapshotError) when a table
misses its window or a required column (SPEC §3). Raw inputs:

    data/raw/faa_cy2025_commercial_enplanements.xlsx, airports.csv, runways.csv, cbsa2025.csv, taf2025.zip
    data/raw/t100/t100_YYYY_MM.zip       ingest/download_t100.py  (24 months, Aug 2024–Jul 2026)
    data/raw/ontime/ontime_YYYY_MM.zip   ingest/download_ontime.py (12 months, Sep 2025–Aug 2026)
    data/raw/geocoder.json               Census Geocoder cache, filled on demand (keyless)
    ingest/runway_capacity.csv           hand-coded from FAA Airport Capacity Profiles, cited per row
"""

from __future__ import annotations

import io
import json
import sys
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geocode import GEOCODER_URL, cbsa_for

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "snapshot"
INGEST = Path(__file__).resolve().parent

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

T100_REQUIRED = ((2024, 8), (2026, 7))       # 24 months ending Jul 2026 (SPEC §3)
ONTIME_TARGET = ((2025, 9), (2026, 8))       # 12 months ending Aug 2026
ONTIME_MIN_MONTHS = 6                        # minimum acceptable (SPEC §3)
TAF_YEARS = (2015, 2045)                     # FY2015–FY2045
SNAPSHOT_MAX_BYTES = 25 * 1024 * 1024
# Airports the golden questions and the brief name: the universe must hold every one.
REQUIRED_AIRPORTS = ["BOS", "BDL", "PVD", "MHT", "PWM", "BTV", "LAX", "SNA", "SFO", "ANC"]

warnings.filterwarnings("ignore", message="Workbook contains no default style")


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


def require_raw(path: Path, table: str, hint: str = "") -> Path:
    if not path.exists():
        raise SnapshotError(f"{table}: raw file missing: {path}" + (f" ({hint})" if hint else ""))
    return path


def window_entry(months: list[tuple[int, int]]) -> dict:
    months = sorted(months)
    return {
        "months": [f"{y}-{m:02d}" for y, m in months],
        "window": f"{len(months)} months, {ym_label(*months[0])}–{ym_label(*months[-1])}",
        "as_of": ym_label(*months[-1]),
    }


def monthly_files(folder: Path, prefix: str) -> dict[tuple[int, int], Path]:
    out = {}
    for f in sorted(folder.glob(f"{prefix}_*.zip")):
        parts = f.stem.split("_")
        out[(int(parts[1]), int(parts[2]))] = f
    return out


def zip_csv(path: Path):
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    return z.open(name)


def write(df: pd.DataFrame, name: str) -> None:
    df.to_parquet(OUT / f"{name}.parquet", index=False, compression="zstd")


def universe() -> pd.DataFrame:
    """The airports table this build wrote (built first in TABLES)."""
    path = OUT / "airports.parquet"
    if not path.exists():
        raise SnapshotError("airports.parquet missing: build the airports table first")
    return pd.read_parquet(path)


# ───────────────────────────── airports ─────────────────────────────

FAA_XLSX = RAW / "faa_cy2025_commercial_enplanements.xlsx"
FAA_URL = ("https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/"
           "arp-cy2025-commercial-service-enplanements.xlsx")
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"
CBSA_CSV = RAW / "cbsa2025.csv"
CBSA_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/cbsa-est2025-alldata.csv"
PRC_CBSA_CSV = RAW / "prc_cbsa2025.csv"
PRC_CBSA_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/prc-cbsa-est2025.csv"
GEOCODER_CACHE = RAW / "geocoder.json"
US_COUNTRIES = {"US", "PR", "GU", "VI", "AS", "MP"}

# Fallback for the golden airports when the Census Geocoder is unreachable (SPEC §3).
# MHT: the 2023 OMB delineation folded Manchester-Nashua (31700) into Boston-Cambridge-Newton (14460).
CBSA_HAND_MAP = {
    "ANC": "11260", "LAX": "31080", "SNA": "31080", "SFO": "41860", "BOS": "14460",
    "BDL": "25540", "PVD": "39300", "MHT": "14460", "PWM": "38860", "BTV": "15540",
}

AIRPORT_COLUMNS = ["iata", "faa_locid", "icao", "name", "city", "state", "faa_region", "hub_size",
                   "is_primary", "lat", "lon", "cbsa_code", "cbsa_name", "runway_count"]


def read_faa_enplanements() -> pd.DataFrame:
    require_raw(FAA_XLSX, "airports", FAA_URL)
    df = pd.read_excel(FAA_XLSX, dtype={"Locid": str})
    require_columns(df, ["RO", "ST", "Locid", "City", "Airport Name", "S/L", "Hub",
                         "CY 25 Enplanements", "CY 24 Enplanements"], "airports(faa xlsx)")
    df = df[df["S/L"].notna() & df["Locid"].notna()].copy()
    df["Locid"] = df["Locid"].astype(str).str.strip()
    return df


def read_cbsa_csv() -> pd.DataFrame:
    """Census PEP Vintage 2025 CBSA totals: the 50 states + DC file plus the Puerto Rico file."""
    frames = []
    for path, url, enc in ((CBSA_CSV, CBSA_URL, "latin-1"), (PRC_CBSA_CSV, PRC_CBSA_URL, "utf-8-sig")):
        require_raw(path, "metro_population", url)
        cbsa = pd.read_csv(path, dtype={"CBSA": str, "MDIV": str, "STCOU": str}, encoding=enc)
        require_columns(cbsa, ["CBSA", "NAME", "LSAD"] + [f"POPESTIMATE{y}" for y in range(2020, 2026)],
                        f"metro_population({path.name})")
        frames.append(cbsa[cbsa["LSAD"].isin(["Metropolitan Statistical Area", "Micropolitan Statistical Area"])])
    return pd.concat(frames, ignore_index=True)


def build_airports() -> dict:
    faa = read_faa_enplanements()
    faa = faa[faa["S/L"].astype(str).str.strip() == "P"].copy()

    oa = pd.read_csv(require_raw(RAW / "airports.csv", "airports", OURAIRPORTS_URL), dtype=str,
                     keep_default_na=False)
    oa = oa[oa["iso_country"].isin(US_COUNTRIES) & (oa["type"] != "closed")]
    type_rank = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}
    oa = oa.assign(_rank=oa["type"].map(type_rank).fillna(9))

    rw = pd.read_csv(require_raw(RAW / "runways.csv", "airports", RUNWAYS_URL), dtype=str, keep_default_na=False)
    rw = rw[(rw["closed"] != "1") & ~rw["le_ident"].str.upper().str.startswith("H")]
    rw_len = pd.to_numeric(rw["length_ft"], errors="coerce").fillna(0)
    runway_counts = rw[rw_len >= 1000].groupby("airport_ident").size()

    def match(locid: str) -> pd.Series | None:
        for col, key in (("local_code", locid), ("iata_code", locid), ("gps_code", "K" + locid)):
            hit = oa[oa[col] == key]
            if len(hit):
                return hit.sort_values("_rank").iloc[0]
        return None

    cbsa_names = dict(zip(*[read_cbsa_csv()[c] for c in ("CBSA", "NAME")]))

    rows = []
    for _, r in faa.iterrows():
        locid = r["Locid"]
        o = match(locid)
        iata = (o["iata_code"] if o is not None and o["iata_code"] else locid)
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
            "cbsa_code": None,
            "cbsa_name": None,
            "runway_count": int(runway_counts.get(o["ident"], 0)) if o is not None else None,
        })
    df = pd.DataFrame(rows, columns=AIRPORT_COLUMNS)

    # CBSA via the Census Geocoder (coordinates → metro/micro area), hand map as the fallback.
    points = {r.faa_locid: (r.lat, r.lon) for r in df.itertuples() if pd.notna(r.lat)}
    geo = cbsa_for(points, GEOCODER_CACHE)
    errors = sorted(k for k, v in geo.items() if "error" in v)
    if len(errors) > 0.1 * len(df):
        raise SnapshotError(f"airports: Census Geocoder failed for {len(errors)} airports (e.g. {errors[:5]}); "
                            f"check {GEOCODER_URL}")
    codes, sources = [], []
    for r in df.itertuples():
        g = geo.get(r.faa_locid, {})
        if g.get("cbsa_code"):
            codes.append(g["cbsa_code"]); sources.append("geocoder")
        elif "error" in g and r.iata in CBSA_HAND_MAP:
            codes.append(CBSA_HAND_MAP[r.iata]); sources.append("hand map")
        else:
            codes.append(None); sources.append(None)
    df["cbsa_code"] = codes
    geo_names = {v["cbsa_code"]: v["cbsa_name"] for v in geo.values() if v.get("cbsa_code")}
    df["cbsa_name"] = [cbsa_names.get(c) or geo_names.get(c) if c else None for c in codes]

    if df["iata"].duplicated().any():
        raise SnapshotError(f"airports: duplicate iata {df[df['iata'].duplicated()]['iata'].tolist()}")
    if len(df) < 370:
        raise SnapshotError(f"airports: only {len(df)} primary airports (expected ≥ 370)")
    absent = [a for a in REQUIRED_AIRPORTS if a not in set(df["iata"])]
    if absent:
        raise SnapshotError(f"airports: required airports missing from the universe: {absent}")
    hand_mismatch = [a for a, c in CBSA_HAND_MAP.items() if a in set(df["iata"])
                     and df.loc[df["iata"] == a, "cbsa_code"].iloc[0] != c]
    if hand_mismatch:
        raise SnapshotError(f"airports: CBSA disagrees with the hand map for {hand_mismatch}")
    unknown_codes = sorted({c for c in codes if c and c not in cbsa_names})

    unmatched = df[df["lat"].isna()]["iata"].tolist()
    no_cbsa = df[df["cbsa_code"].isna()]["iata"].tolist()
    df = df.sort_values("iata").reset_index(drop=True)
    write(df, "airports")
    notes = [(f"CBSA: {sources.count('geocoder')} from the Census Geocoder, {sources.count('hand map')} from the "
              f"hand map, {len(no_cbsa)} outside any metro/micro area: {no_cbsa}")]
    if unmatched:
        notes.append(f"{len(unmatched)} airports without an OurAirports match: {unmatched}")
    if errors:
        notes.append(f"Census Geocoder errors (retried next build): {errors}")
    if unknown_codes:
        notes.append(f"CBSA codes absent from the PEP 2025 CSV: {unknown_codes}")
    return {
        "source": "FAA CY2025 commercial-service enplanements (universe: S/L = P) + OurAirports airports/runways"
                  " + CBSA via Census Geocoder coordinates API (hand-map fallback for golden airports)",
        "url": [FAA_URL, OURAIRPORTS_URL, RUNWAYS_URL, GEOCODER_URL, CBSA_URL, PRC_CBSA_URL],
        "as_of": "CY2025",
        "window": "current",
        "rows": len(df),
        "notes": notes,
    }


# ───────────────────────────── enplanements ─────────────────────────────

def build_enplanements() -> dict:
    faa = read_faa_enplanements()
    faa = faa[faa["S/L"].astype(str).str.strip() == "P"]
    iata_of = dict(zip(universe()["faa_locid"], universe()["iata"]))
    df = pd.DataFrame({
        "iata": faa["Locid"].map(iata_of),
        "cy2024": pd.to_numeric(faa["CY 24 Enplanements"], errors="coerce").round().astype("Int64"),
        "cy2025": pd.to_numeric(faa["CY 25 Enplanements"], errors="coerce").round().astype("Int64"),
    })
    if df["iata"].isna().any():
        raise SnapshotError("enplanements: FAA rows without a universe airport")
    if df["cy2025"].isna().any():
        raise SnapshotError(f"enplanements: CY2025 missing for {df[df['cy2025'].isna()]['iata'].tolist()}")
    base = df["cy2024"].astype("float64")
    df["yoy_pct"] = (100.0 * (df["cy2025"].astype("float64") / base.where(base > 0) - 1.0)).round(4)
    df = df.sort_values("iata").reset_index(drop=True)
    write(df, "enplanements")
    return {
        "source": "FAA CY2025 commercial-service enplanements (CY2024 and CY2025 columns), primary airports",
        "url": FAA_URL,
        "as_of": "CY2025",
        "window": "CY2024–CY2025",
        "rows": len(df),
        "notes": ["yoy_pct is in percent: 100 × (cy2025 / cy2024 − 1)"],
    }


# ───────────────────────────── taf ─────────────────────────────

TAF_ZIP = RAW / "taf2025.zip"
TAF_URL = "https://taf.faa.gov/Downloads/APO100_TAF_Final_2025.zip"
TAF_ENPL_COLS = ["locid", "scenario", "ayear", "aac", "aat", "commuter", "us_flag", "frgn_flag"]
TAF_OPS_COLS = ["locid", "scenario", "ayear", "itn_Ac", "itn_at", "itn_ga", "itn_mil"]
TAF_COLUMNS = ["iata", "fiscal_year", "is_forecast", "enplanements_total", "enplanements_international",
               "enplanements_aac", "enplanements_aat", "enplanements_commuter",
               "ops_air_carrier", "ops_air_taxi", "ops_itinerant_total"]


def read_taf_sheet(name: str, cols: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(require_raw(TAF_ZIP, "taf", TAF_URL)) as z:
        if name not in z.namelist():
            raise SnapshotError(f"taf: {name} not in {TAF_ZIP.name}")
        df = pd.read_excel(io.BytesIO(z.read(name)), dtype={"locid": str})
    require_columns(df, cols, f"taf({name})")
    df = df[cols].copy()
    df["locid"] = df["locid"].astype(str).str.strip()   # TAF locids are space-padded
    return df


def taf_enplanements_total(row) -> int:
    """SPEC §3: total = aac + aat + commuter + us_flag + frgn_flag (international included)."""
    return int(row["aac"] + row["aat"] + row["commuter"] + row["us_flag"] + row["frgn_flag"])


def build_taf() -> dict:
    enpl = read_taf_sheet("Enplanements.xlsx", TAF_ENPL_COLS)
    ops = read_taf_sheet("AirportsOperations.xlsx", TAF_OPS_COLS)
    lo, hi = TAF_YEARS
    enpl = enpl[enpl["ayear"].between(lo, hi)]
    ops = ops[ops["ayear"].between(lo, hi)]
    df = enpl.merge(ops, on=["locid", "ayear"], how="outer", suffixes=("", "_ops"))
    df["scenario"] = df["scenario"].fillna(df["scenario_ops"])
    u = universe()
    iata_of = dict(zip(u["faa_locid"], u["iata"]))
    df = df[df["locid"].isin(iata_of)].copy()
    num = ["aac", "aat", "commuter", "us_flag", "frgn_flag", "itn_Ac", "itn_at", "itn_ga", "itn_mil"]
    df[num] = df[num].fillna(0).astype("int64")
    out = pd.DataFrame({
        "iata": df["locid"].map(iata_of),
        "fiscal_year": df["ayear"].astype("int32"),
        "is_forecast": df["scenario"].astype(int) == 1,
        "enplanements_total": df["aac"] + df["aat"] + df["commuter"] + df["us_flag"] + df["frgn_flag"],
        "enplanements_international": df["us_flag"] + df["frgn_flag"],
        "enplanements_aac": df["aac"],
        "enplanements_aat": df["aat"],
        "enplanements_commuter": df["commuter"],
        "ops_air_carrier": df["itn_Ac"],
        "ops_air_taxi": df["itn_at"],
        "ops_itinerant_total": df["itn_Ac"] + df["itn_at"] + df["itn_ga"] + df["itn_mil"],
    })[TAF_COLUMNS]

    # Coverage: every fiscal year in the window for every TAF airport; FY2024 is the last actual.
    years = sorted(out["fiscal_year"].unique())
    if years != list(range(lo, hi + 1)):
        raise SnapshotError(f"taf: fiscal years {years[0]}–{years[-1]} do not cover FY{lo}–FY{hi}")
    if out.groupby("iata").size().ne(hi - lo + 1).any():
        raise SnapshotError("taf: some airports miss fiscal years in the window")
    last_actual = int(out.loc[~out["is_forecast"], "fiscal_year"].max())
    if last_actual != 2024:
        raise SnapshotError(f"taf: last actual fiscal year is FY{last_actual}, expected FY2024")
    missing = sorted(set(u["iata"]) - set(out["iata"]))
    absent_required = [a for a in REQUIRED_AIRPORTS if a in missing]
    if absent_required:
        raise SnapshotError(f"taf: required airports missing: {absent_required}")

    # Diagnostic only (SPEC §3): TAF FY2024 total vs FAA CY2024. Fiscal ≠ calendar year, so never fail.
    cy = pd.read_parquet(OUT / "enplanements.parquet").set_index("iata")["cy2024"] \
        if (OUT / "enplanements.parquet").exists() else pd.Series(dtype="float64")
    fy24 = out[out["fiscal_year"] == 2024].set_index("iata")["enplanements_total"]
    both = pd.concat([fy24.rename("fy2024"), cy.rename("cy2024")], axis=1, join="inner").dropna()
    both = both[both["cy2024"] > 100_000]
    gap = (both["fy2024"] / both["cy2024"].astype("float64") - 1.0).abs()
    diag = (f"diagnostic: TAF FY2024 total vs FAA CY2024 for {len(both)} airports with > 100k CY2024 "
            f"enplanements: median gap {100 * gap.median():.1f}%, {int((gap > 0.10).sum())} beyond 10% "
            f"(fiscal and calendar years cover different periods; not a failure)")
    if "SFO" in both.index:
        diag += f"; SFO FY2024 {int(both.loc['SFO', 'fy2024']):,} vs CY2024 {int(both.loc['SFO', 'cy2024']):,}"
    print(f"  WARNING {diag}", flush=True)

    out = out.sort_values(["iata", "fiscal_year"]).reset_index(drop=True)
    write(out, "taf")
    return {
        "source": "FAA Terminal Area Forecast 2025 (Enplanements.xlsx + AirportsOperations.xlsx), universe airports",
        "url": TAF_URL,
        "as_of": "TAF 2025 (actuals to FY2024)",
        "window": f"FY{lo}–FY{hi} (fiscal years Oct–Sep; FY{lo}–FY2024 actual, FY2025–FY{hi} forecast)",
        "fiscal_years": [lo, hi],
        "rows": len(out),
        "notes": [
            "enplanements_total = aac + aat + commuter + us_flag + frgn_flag (international included)",
            "ops_air_carrier = itinerant air-carrier ops; ops_itinerant_total = air carrier + air taxi + GA + military",
            f"universe airports absent from TAF 2025: {missing}",
            diag,
        ],
    }


# ───────────────────────────── t100_routes ─────────────────────────────

T100_URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45"
T100_RAW_COLS = ["YEAR", "MONTH", "ORIGIN", "ORIGIN_COUNTRY", "DEST", "DEST_COUNTRY", "CLASS", "DISTANCE",
                 "DEPARTURES_PERFORMED", "DEPARTURES_SCHEDULED", "SEATS", "PASSENGERS", "FREIGHT"]
T100_COLUMNS = ["year", "month", "origin", "origin_country", "dest", "dest_country", "service_class",
                "distance_mi", "departures_performed", "departures_scheduled", "seats", "passengers", "freight_lbs"]


def read_t100_month(path: Path) -> pd.DataFrame:
    df = pd.read_csv(zip_csv(path), dtype={"ORIGIN": str, "DEST": str, "CLASS": str,
                                           "ORIGIN_COUNTRY": str, "DEST_COUNTRY": str},
                     keep_default_na=False, na_values=[""])
    require_columns(df, T100_RAW_COLS, f"t100_routes({path.name})")
    return df[T100_RAW_COLS]


def build_t100_routes() -> dict:
    files = monthly_files(RAW / "t100", "t100")
    wanted = months_between(*T100_REQUIRED)
    missing = [ym for ym in wanted if ym not in files]
    if missing:
        raise SnapshotError(f"t100_routes: missing required months {[f'{y}-{m:02d}' for y, m in missing]} "
                            f"(run ingest/download_t100.py)")
    frames = []
    for ym in wanted:
        f = read_t100_month(files[ym])
        if set(zip(f["YEAR"], f["MONTH"])) != {ym}:
            raise SnapshotError(f"t100_routes: {files[ym].name} holds {sorted(set(zip(f['YEAR'], f['MONTH'])))}")
        frames.append(f)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["DEPARTURES_PERFORMED"] > 0]
    agg = (raw.groupby(["YEAR", "MONTH", "ORIGIN", "ORIGIN_COUNTRY", "DEST", "DEST_COUNTRY", "CLASS"],
                       as_index=False, dropna=False)
           .agg(DISTANCE=("DISTANCE", "max"),
                DEPARTURES_PERFORMED=("DEPARTURES_PERFORMED", "sum"),
                DEPARTURES_SCHEDULED=("DEPARTURES_SCHEDULED", "sum"),
                SEATS=("SEATS", "sum"), PASSENGERS=("PASSENGERS", "sum"), FREIGHT=("FREIGHT", "sum")))
    agg.columns = T100_COLUMNS
    for c in ["year", "month"]:
        agg[c] = agg[c].astype("int32")
    for c in ["distance_mi", "departures_performed", "departures_scheduled", "seats", "passengers", "freight_lbs"]:
        agg[c] = agg[c].round().astype("int64")
    if agg["dest_country"].isna().mean() > 0.01:
        raise SnapshotError("t100_routes: dest_country is empty on > 1% of rows")
    agg = agg.sort_values(["year", "month", "origin", "dest", "service_class"]).reset_index(drop=True)
    write(agg, "t100_routes")
    return {
        "source": "BTS TranStats T-100 Segment (All Carriers), carrier and aircraft aggregated away",
        "url": T100_URL,
        "rows": len(agg),
        **window_entry(wanted),
        "notes": [("rows with departures_performed == 0 dropped; service_class F = scheduled passenger, "
                   "G = scheduled cargo, L/P = non-scheduled")],
    }


# ───────────────────────────── ontime_airport_month ─────────────────────────────

ONTIME_URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ&QO_fu146_anzr=Nv4%20Pn44vr45"
ONTIME_RAW_COLS = ["FL_DATE", "ORIGIN", "DEP_DELAY", "DEP_DEL15", "TAXI_OUT", "CANCELLED", "NAS_DELAY"]
ONTIME_COLUMNS = ["origin", "year", "month", "flights", "flights_operated", "dep_del15_share", "avg_taxi_out_min",
                  "cancel_rate", "nas_delay_min_per_flight", "avg_dep_delay_min"]


def aggregate_ontime(raw: pd.DataFrame) -> pd.DataFrame:
    """Flight rows → origin × month. Shares and rates are fractions (0–1).

    flights            scheduled reporting-carrier departures (cancelled included)
    flights_operated   flights not cancelled
    dep_del15_share    share of operated flights departing ≥ 15 min late
    avg_taxi_out_min   mean taxi-out minutes over operated flights
    cancel_rate        cancelled / flights
    nas_delay_min_per_flight  NAS-attributed delay minutes / flights_operated
    avg_dep_delay_min  mean departure delay minutes (early departures count as negative)
    """
    require_columns(raw, ONTIME_RAW_COLS, "ontime_airport_month")
    date = raw["FL_DATE"].astype(str).str.split(" ").str[0]
    if date.str.contains("/").all():
        parts = date.str.split("/")
        month, year = parts.str[0].astype(int), parts.str[2].astype(int)
    else:
        d = pd.to_datetime(date)
        month, year = d.dt.month, d.dt.year
    cancelled = pd.to_numeric(raw["CANCELLED"], errors="coerce").fillna(0)
    df = pd.DataFrame({
        "origin": raw["ORIGIN"].astype(str),
        "year": year.astype("int32"),
        "month": month.astype("int32"),
        "cancelled": cancelled,
        "operated": 1.0 - cancelled,
        "del15": pd.to_numeric(raw["DEP_DEL15"], errors="coerce"),
        "taxi_out": pd.to_numeric(raw["TAXI_OUT"], errors="coerce"),
        "nas": pd.to_numeric(raw["NAS_DELAY"], errors="coerce").fillna(0).where(cancelled == 0, 0),
        "dep_delay": pd.to_numeric(raw["DEP_DELAY"], errors="coerce"),
    })
    g = df.groupby(["origin", "year", "month"], sort=True)
    out = pd.DataFrame({
        "flights": g.size(),
        "flights_operated": g["operated"].sum(),
        "dep_del15_share": g["del15"].mean(),
        "avg_taxi_out_min": g["taxi_out"].mean(),
        "cancel_rate": g["cancelled"].mean(),
        "nas_sum": g["nas"].sum(),
        "avg_dep_delay_min": g["dep_delay"].mean(),
    }).reset_index()
    out["nas_delay_min_per_flight"] = out["nas_sum"] / out["flights_operated"].where(out["flights_operated"] > 0)
    out["flights"] = out["flights"].astype("int64")
    out["flights_operated"] = out["flights_operated"].round().astype("int64")
    return out[ONTIME_COLUMNS]


def read_ontime_month(path: Path) -> pd.DataFrame:
    with zip_csv(path) as f:
        head = f.readline().decode("utf-8-sig").strip().split(",")
    missing = [c for c in ONTIME_RAW_COLS if c not in head]
    if missing:
        raise SnapshotError(f"ontime_airport_month({path.name}): missing required columns {missing}")
    with zip_csv(path) as f:
        raw = pd.read_csv(f, usecols=ONTIME_RAW_COLS, dtype={"ORIGIN": str, "FL_DATE": str})
    return aggregate_ontime(raw)


def build_ontime_airport_month() -> dict:
    files = monthly_files(RAW / "ontime", "ontime")
    wanted = months_between(*ONTIME_TARGET)
    have = [ym for ym in wanted if ym in files]
    if len(have) < ONTIME_MIN_MONTHS:
        raise SnapshotError(f"ontime_airport_month: only {len(have)} of {len(wanted)} target months present "
                            f"(minimum {ONTIME_MIN_MONTHS}; run ingest/download_ontime.py)")
    frames = []
    for ym in have:
        print(f"  ontime {ym[0]}-{ym[1]:02d}", flush=True)
        agg = read_ontime_month(files[ym])
        got = set(zip(agg["year"], agg["month"]))
        if got != {ym}:
            raise SnapshotError(f"ontime_airport_month: {files[ym].name} holds months {sorted(got)}")
        frames.append(agg)
    df = pd.concat(frames, ignore_index=True).sort_values(["year", "month", "origin"]).reset_index(drop=True)
    write(df, "ontime_airport_month")
    absent = [f"{y}-{m:02d}" for y, m in wanted if (y, m) not in have]
    notes = [("reporting carriers only (the largest US carriers), domestic flights; shares and rates are "
              "fractions 0–1; nas_delay_min_per_flight = NAS-attributed delay minutes / operated flights")]
    if absent:
        notes.append(f"target months not yet downloaded: {absent}")
    return {
        "source": "BTS Reporting Carrier On-Time Performance, pre-aggregated to origin airport × month",
        "url": ONTIME_URL,
        "rows": len(df),
        **window_entry(have),
        "notes": notes,
    }


# ───────────────────────────── metro_population ─────────────────────────────

def build_metro_population() -> dict:
    cbsa = read_cbsa_csv()
    df = pd.DataFrame({"cbsa_code": cbsa["CBSA"].astype(str), "cbsa_name": cbsa["NAME"],
                       "lsad": cbsa["LSAD"].map({"Metropolitan Statistical Area": "metro",
                                                  "Micropolitan Statistical Area": "micro"})})
    for y in range(2020, 2026):
        df[f"pop_{y}"] = pd.to_numeric(cbsa[f"POPESTIMATE{y}"], errors="raise").astype("int64").values
    if df["cbsa_code"].duplicated().any():
        raise SnapshotError("metro_population: duplicate CBSA codes")
    df = df.sort_values("cbsa_code").reset_index(drop=True)
    write(df, "metro_population")
    codes = set(df["cbsa_code"])
    u = universe()
    unmatched = sorted(set(u["cbsa_code"].dropna()) - codes)
    if unmatched:
        raise SnapshotError(f"metro_population: airport CBSA codes without a population row: {unmatched}")
    return {
        "source": "Census Population Estimates Program, CBSA totals (Vintage 2025), metro + micro areas incl. Puerto Rico",
        "url": [CBSA_URL, PRC_CBSA_URL],
        "as_of": "Jul 1, 2025 estimate (Vintage 2025)",
        "window": "2020–2025",
        "rows": len(df),
        "notes": [f"{int(u['cbsa_code'].notna().sum())} of {len(u)} universe airports map to a CBSA"],
    }


# ───────────────────────────── runway_capacity ─────────────────────────────

RUNWAY_CAPACITY_CSV = INGEST / "runway_capacity.csv"
RUNWAY_CAPACITY_COLUMNS = ["iata", "vfr_arrivals_hr", "ifr_arrivals_hr", "vfr_departures_hr", "ifr_departures_hr",
                           "source_note"]
CAPACITY_PROFILES_URL = "https://www.faa.gov/airports/planning_capacity/profiles"


def build_runway_capacity() -> dict:
    df = pd.read_csv(require_raw(RUNWAY_CAPACITY_CSV, "runway_capacity"), dtype={"iata": str})
    require_columns(df, RUNWAY_CAPACITY_COLUMNS + ["source_url"], "runway_capacity")
    rates = ["vfr_arrivals_hr", "ifr_arrivals_hr", "vfr_departures_hr", "ifr_departures_hr"]
    if df[rates].isna().any().any() or df["source_note"].isna().any() or df["source_url"].isna().any():
        raise SnapshotError("runway_capacity: every row needs all four rates and a citation")
    for v, i in (("vfr_arrivals_hr", "ifr_arrivals_hr"), ("vfr_departures_hr", "ifr_departures_hr")):
        if (df[i] > df[v]).any():
            raise SnapshotError(f"runway_capacity: {i} above {v} for {df[df[i] > df[v]]['iata'].tolist()}")
    stray = sorted(set(df["iata"]) - set(universe()["iata"]))
    if stray:
        raise SnapshotError(f"runway_capacity: airports outside the universe: {stray}")
    df["ifr_arrival_drop_pct"] = (100.0 * (1 - df["ifr_arrivals_hr"] / df["vfr_arrivals_hr"])).round(1)
    df = df.sort_values("iata").reset_index(drop=True)
    write(df, "runway_capacity")
    return {
        "source": "FAA Airport Capacity Profiles: ATC facility-reported hourly rates (arrivals, departures), "
                  "hand-coded per airport",
        "url": CAPACITY_PROFILES_URL,
        "as_of": "FAA Airport Capacity Profiles 2014 (LAX, SNA); 2019 editions for SFO and BOS",
        "window": "static",
        "rows": len(df),
        "notes": [
            "covers SFO, LAX, SNA and BOS only; any other airport has no runway_capacity row",
            ("SFO and BOS: the FAA no longer publishes their 2014 profiles, so rates come from the 2019 "
             "editions (2014 Table 1 totals cited in source_note as a cross-check)"),
            "ifr_arrival_drop_pct = 100 × (1 − ifr_arrivals_hr / vfr_arrivals_hr)",
        ],
    }


# ───────────────────────────── driver ─────────────────────────────

TABLES = {
    "airports": build_airports,
    "enplanements": build_enplanements,
    "taf": build_taf,
    "t100_routes": build_t100_routes,
    "ontime_airport_month": build_ontime_airport_month,
    "metro_population": build_metro_population,
    "runway_capacity": build_runway_capacity,
}


def check_size() -> int:
    total = sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    if total > SNAPSHOT_MAX_BYTES:
        raise SnapshotError(f"data/snapshot is {total / 1e6:.1f} MB (limit {SNAPSHOT_MAX_BYTES / 1024 / 1024:.0f} MB)")
    return total


def main(only: list[str] | None = None) -> None:
    unknown = [t for t in (only or []) if t not in TABLES]
    if unknown:
        raise SnapshotError(f"unknown tables {unknown}; choose from {list(TABLES)}")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if (only and manifest_path.exists()) else {"tables": {}}
    built_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, fn in TABLES.items():
        if only and name not in only:
            continue
        print(f"building {name} …", flush=True)
        entry = fn()
        entry["built_at"] = built_at
        manifest["tables"][name] = entry
        print(f"  {name}: {entry['rows']} rows, {entry.get('window', '')}", flush=True)
    missing = [t for t in TABLES if t not in manifest["tables"] or not (OUT / f"{t}.parquet").exists()]
    if missing and not only:
        raise SnapshotError(f"tables missing after build: {missing}")
    manifest["built_at"] = built_at
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    total = check_size()
    print(f"wrote {manifest_path} (snapshot {total / 1e6:.1f} MB)")


if __name__ == "__main__":
    try:
        main(sys.argv[1:] or None)
    except SnapshotError as e:
        print(f"SNAPSHOT FAILED: {e}", file=sys.stderr)
        sys.exit(1)
