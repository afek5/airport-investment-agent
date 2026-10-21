"""Independent pandas recomputation of the G1–G4 figures straight from data/snapshot/*.parquet.

Deliberately shares no code with backend/app/analytics: it reads the Parquet files with pandas
(no DuckDB, no app.snapshot) and re-derives each figure from the SPEC §4 definitions, so a
golden test passing means two separate implementations of the SPEC agree on the real Snapshot.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshot"

# SPEC §4 metric table: metric → (Pillar, weight in Pillar)
METRICS = {
    "forecast_cagr": ("momentum", 0.60), "enpl_yoy": ("momentum", 0.40),
    "load_factor": ("pressure", 0.40), "delay_share": ("pressure", 0.30), "taxi_out": ("pressure", 0.30),
    "enplanements": ("scale", 0.70), "metro_pop": ("scale", 0.30),
}
PILLARS = ("momentum", "pressure", "scale")
DEFAULT_WEIGHTS = {"momentum": 0.35, "pressure": 0.40, "scale": 0.25}
NEW_ENGLAND = ["CT", "ME", "MA", "NH", "RI", "VT"]
EUROPE = {"AD", "AL", "AT", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GI",
          "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK", "MT", "NL", "NO", "PL",
          "PT", "RO", "RS", "SE", "SI", "SK", "SM", "UA", "XK"}


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    return pd.read_parquet(SNAPSHOT / f"{name}.parquet")


def last_n_months(df: pd.DataFrame, n: int = 12, skip: int = 0) -> pd.DataFrame:
    ym = sorted(set(zip(df["year"], df["month"])), reverse=True)[skip:skip + n]
    keys = {y * 100 + m for y, m in ym}
    return df[(df["year"] * 100 + df["month"]).isin(keys)]


def universe() -> pd.DataFrame:
    a = table("airports")
    return a[a["is_primary"]].drop_duplicates("iata").set_index("iata").sort_index()


def raw_metrics() -> pd.DataFrame:
    """The seven score metrics plus the congestion fields, one row per Primary Airport."""
    u = universe()
    out = pd.DataFrame(index=u.index)

    t = last_n_months(table("t100_routes"))
    f = t[t["service_class"] == "F"].groupby("origin")[["passengers", "seats"]].sum()
    f = f[f["seats"] > 0]
    out["load_factor"] = (100 * f["passengers"] / f["seats"]).reindex(u.index)
    out["departures_12m"] = t.groupby("origin")["departures_performed"].sum().reindex(u.index)

    o = last_n_months(table("ontime_airport_month"))
    w = o["flights"]
    g = o.assign(d=o["dep_del15_share"] * w, x=o["avg_taxi_out_min"] * w, c=o["cancel_rate"] * w,
                 n=o["nas_delay_min_per_flight"] * w).groupby("origin")[["flights", "d", "x", "c", "n"]].sum()
    g = g[g["flights"] >= 1000]  # SPEC §4: thin On-Time samples are unmeasured
    out["delay_share"] = (100 * g["d"] / g["flights"]).reindex(u.index)  # stored as fractions 0–1
    out["taxi_out"] = (g["x"] / g["flights"]).reindex(u.index)
    out["cancel_rate"] = (100 * g["c"] / g["flights"]).reindex(u.index)
    out["nas_delay_min_per_flight"] = (g["n"] / g["flights"]).reindex(u.index)

    taf = table("taf").pivot_table(index="iata", columns="fiscal_year", values="enplanements_total", aggfunc="max")
    base, horizon = taf[2024], taf[2035]
    out["forecast_cagr"] = (100 * ((horizon / base.where(base > 0)) ** (1 / 11) - 1)).reindex(u.index)

    e = table("enplanements").drop_duplicates("iata").set_index("iata")
    cy24, cy25 = e["cy2024"].astype("float64"), e["cy2025"].astype("float64")
    out["enplanements"] = cy25.reindex(u.index)
    out["enpl_yoy"] = (100 * (cy25 / cy24.where(cy24 > 0) - 1)).reindex(u.index)

    pop = table("metro_population").drop_duplicates("cbsa_code").set_index("cbsa_code")["pop_2025"]
    out["metro_pop"] = u["cbsa_code"].map(pop).astype("float64")
    out["runway_count"] = u["runway_count"].astype("float64")
    return out


def pct(s: pd.Series) -> pd.Series:
    return s.astype("float64").rank(pct=True, method="average") * 100


def scores(weights: dict[str, float] = DEFAULT_WEIGHTS) -> pd.DataFrame:
    """Investment Opportunity Score per Primary Airport (NaN = not ranked), with Pillars and Coverage."""
    m = raw_metrics()
    total = sum(weights.values())
    w = {p: weights[p] / total for p in PILLARS}
    p = pd.DataFrame({k: pct(m[k]) for k in METRICS})
    out = pd.DataFrame(index=m.index)
    out["measured"] = p.notna().sum(axis=1)
    for pillar in PILLARS:
        keys = [k for k, (pp, _) in METRICS.items() if pp == pillar]
        weights_in = np.array([METRICS[k][1] for k in keys])
        filled = p[keys].fillna(50.0).to_numpy()  # median imputation at the 50th percentile
        val = filled @ weights_in / weights_in.sum()
        out[pillar] = np.where(p[keys].notna().any(axis=1), val, np.nan)
    ok = out[list(PILLARS)].notna().all(axis=1)
    geo = sum(w[q] * np.log(np.maximum(out[q], 1.0)) for q in PILLARS)
    out["score"] = np.where(ok, np.exp(geo), np.nan)
    return out


def ranking(states: list[str], weights: dict[str, float] = DEFAULT_WEIGHTS) -> list[tuple[str, float]]:
    s = scores(weights)
    states_of = universe()["state"]
    s = s[states_of.reindex(s.index).isin(states) & s["score"].notna()]
    return sorted(((i, float(v)) for i, v in s["score"].items()), key=lambda kv: (-kv[1], kv[0]))


def route_mix(iata: str, min_miles: int = 3000) -> dict:
    t = last_n_months(table("t100_routes"))
    t = t[t["origin"] == iata]
    lh = t["distance_mi"] >= min_miles
    f = t["service_class"] == "F"
    cargo = t["service_class"].isin(["G", "P"])

    def share(num: float, den: float) -> float:
        return round(100 * num / den, 1) if den else 0.0

    deps = t["departures_performed"]
    top = (t[f & lh].groupby("dest")["departures_performed"].sum().reset_index()
           .sort_values(["departures_performed", "dest"], ascending=[False, True]).head(10))
    return {
        "passenger_departures": (int(deps[f & lh].sum()), int(deps[f].sum()), share(deps[f & lh].sum(), deps[f].sum())),
        "passenger_weighted": (int(t.loc[f & lh, "passengers"].sum()), int(t.loc[f, "passengers"].sum()),
                               share(t.loc[f & lh, "passengers"].sum(), t.loc[f, "passengers"].sum())),
        "cargo_inclusive": (int(deps[lh].sum()), int(deps.sum()), share(deps[lh].sum(), deps.sum())),
        "all_cargo": (int(deps[cargo & lh].sum()), int(deps[cargo].sum()), share(deps[cargo & lh].sum(), deps[cargo].sum())),
        "non_passenger_share": share(deps[~f].sum(), deps.sum()),
        "top_destinations": list(top["dest"]),
    }


def congestion(iatas: list[str]) -> dict[str, dict[str, tuple[float, float | None]]]:
    """metric → airport → (value, national percentile), plus the congestion_index."""
    m = raw_metrics()
    m["monthly_departures"] = m["departures_12m"] / 12
    m["deps_per_runway_day"] = m["departures_12m"] / 365.25 / m["runway_count"].where(m["runway_count"] > 0)
    keys = ["delay_share", "taxi_out", "cancel_rate", "nas_delay_min_per_flight", "monthly_departures",
            "deps_per_runway_day", "load_factor"]
    out = {k: {c: (float(m.at[c, k]), float(pct(m[k])[c])) for c in iatas} for k in keys}
    out["congestion_index"] = {
        c: (sum(out[k][c][1] for k in ("delay_share", "taxi_out", "nas_delay_min_per_flight")) / 3, None)
        for c in iatas}
    return out


def unmet(iata: str) -> dict:
    m = raw_metrics()
    t = last_n_months(table("t100_routes"))
    rm = (t[t["service_class"] == "F"].groupby(["origin", "dest", "year", "month"])[["passengers", "seats"]].sum()
          .reset_index())
    rm = rm[rm["seats"] > 0]
    rm["lf"] = rm["passengers"] / rm["seats"]
    full_share = rm.assign(full=rm["lf"] > 0.85).groupby("origin")["full"].mean() * 100

    mine = rm[rm["origin"] == iata]
    low = high = 0.0
    for lf, pax in zip(mine["lf"], mine["passengers"]):
        if 0.85 < lf <= 0.90:
            low, high = low + 0.02 * pax, high + 0.05 * pax
        elif 0.90 < lf <= 0.95:
            low, high = low + 0.05 * pax, high + 0.10 * pax
        elif lf > 0.95:
            low, high = low + 0.10 * pax, high + 0.15 * pax

    cap = table("runway_capacity").set_index("iata")
    vfr, ifr = float(cap.at[iata, "vfr_arrivals_hr"]), float(cap.at[iata, "ifr_arrivals_hr"])

    taf = table("taf")
    taf = taf[taf["iata"] == iata].set_index("fiscal_year")
    e0, e1 = float(taf.at[2024, "enplanements_total"]), float(taf.at[2030, "enplanements_total"])
    o0, o1 = float(taf.at[2024, "ops_air_carrier"]), float(taf.at[2030, "ops_air_carrier"])

    def vs_median(col: pd.Series) -> tuple[float, float]:
        return float(col[iata]), float(col.dropna().median())

    return {
        "delay_share": vs_median(m["delay_share"]),
        "taxi_out": vs_median(m["taxi_out"]),
        "nas_delay_min_per_flight": vs_median(m["nas_delay_min_per_flight"]),
        "full_route_month_share": vs_median(full_share.reindex(m.index)),
        "ifr_arrival_drop": 100 * (vfr - ifr) / vfr,
        "forecast_gap": {"enplanements_from": e0, "enplanements_to": e1, "enplanements_pct": 100 * (e1 - e0) / e0,
                         "ops_from": o0, "ops_to": o1, "ops_pct": 100 * (o1 - o0) / o0},
        "spill": (round(low), round(high)),
    }


def close(a: float | None, b: float | None, tol: float = 0.051) -> bool:
    """Tool values are rounded to 1 decimal; allow that rounding."""
    if a is None or b is None or (isinstance(b, float) and math.isnan(b)):
        return a is None and (b is None or math.isnan(b))
    return abs(float(a) - float(b)) <= tol


def bos_europe_summer_2026() -> dict[str, int]:
    """G6: departures BOS → Europe in summer 2026 (Jun–Aug; the Snapshot ends Jul 2026)."""
    t = table("t100_routes")
    t = t[(t["origin"] == "BOS") & t["dest_country"].isin(EUROPE) & (t["year"] == 2026) & t["month"].isin([6, 7, 8])]
    return {"scheduled_passenger": int(t.loc[t["service_class"] == "F", "departures_performed"].sum()),
            "all_classes": int(t["departures_performed"].sum())}
