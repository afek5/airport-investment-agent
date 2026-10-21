"""Raw metric values per Primary Airport, read from the Snapshot (SPEC §4 metric table).

`load_metrics()` returns one row per universe airport with the seven score metrics plus the
extra congestion and demand fields the other tools need. A table missing from the Snapshot
makes its metrics null (and is named in `MetricFrame.missing_tables`), it never crashes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.analytics.common import has_table, in_months, last_months, table_source, window_label
from app.analytics.constants import (
    MIN_ONTIME_DEPARTURES,
    ONTIME_WINDOW_MONTHS,
    PASSENGER_CLASS,
    T100_WINDOW_MONTHS,
    TAF_BASE_FY,
    TAF_HORIZON_FY,
)
from app.contracts import Source
from app.snapshot import get_conn

AIRPORT_COLS = ["iata", "name", "state", "faa_region", "hub_size", "cbsa_code", "runway_count"]


@dataclass
class MetricFrame:
    df: pd.DataFrame  # indexed by iata
    t100_months: list[tuple[int, int]]
    ontime_months: list[tuple[int, int]]
    missing_tables: list[str] = field(default_factory=list)

    @property
    def t100_window(self) -> str:
        return window_label(self.t100_months)

    @property
    def ontime_window(self) -> str:
        return window_label(self.ontime_months)

    def score_sources(self) -> list[Source]:
        out = [
            table_source("airports"),
            table_source("enplanements"),
            table_source("taf", window=f"FY{TAF_BASE_FY} actual → FY{TAF_HORIZON_FY} forecast"),
            table_source("t100_routes", window=self.t100_window,
                         as_of=self.t100_window.split("–")[-1] if self.t100_months else None),
            table_source("ontime_airport_month", window=self.ontime_window,
                         as_of=self.ontime_window.split("–")[-1] if self.ontime_months else None),
            table_source("metro_population"),
        ]
        return [s for s in out if s is not None]


def as_percent(s: pd.Series) -> pd.Series:
    """Snapshot shares/rates may be stored as fractions (0–1) or percents (0–100); return percents.

    A whole column at or below 1.0 is read as fractions. (A national delay share or cancel rate that
    never exceeds 1 % across 12 months is not a realistic percent column.)
    """
    s = s.astype("float64")
    valid = s.dropna()
    return s * 100.0 if len(valid) and valid.max() <= 1.0 else s


def _query_df(conn, sql: str, params: list | None = None) -> pd.DataFrame:
    return conn.execute(sql, params or []).df()


def load_metrics(conn=None) -> MetricFrame:
    conn = conn or get_conn()
    missing = [t for t in ("airports", "enplanements", "taf", "t100_routes", "ontime_airport_month",
                           "metro_population") if not has_table(conn, t)]
    if "airports" in missing:
        raise ValueError("The Snapshot has no airports table")

    df = _query_df(conn, f"SELECT {', '.join(AIRPORT_COLS)} FROM airports WHERE is_primary ORDER BY iata")
    df = df.drop_duplicates("iata").set_index("iata")

    # ── T-100: Load Factor (class F), departures (all classes), passengers/seats growth ──
    t100_months = last_months(conn, "t100_routes", T100_WINDOW_MONTHS)
    prior_months = last_months(conn, "t100_routes", T100_WINDOW_MONTHS, offset=T100_WINDOW_MONTHS)
    for col in ("load_factor", "departures_12m", "pax_12m", "seats_12m", "pax_prior_12m", "seats_prior_12m"):
        df[col] = float("nan")
    if t100_months:
        pred, keys = in_months(t100_months)
        t = _query_df(conn, f"""
            SELECT origin AS iata,
                   SUM(CASE WHEN service_class = ? THEN passengers ELSE 0 END) AS pax_12m,
                   SUM(CASE WHEN service_class = ? THEN seats ELSE 0 END) AS seats_12m,
                   SUM(departures_performed) AS departures_12m
            FROM t100_routes WHERE {pred} GROUP BY origin""", [PASSENGER_CLASS, PASSENGER_CLASS, *keys])
        t = t.set_index("iata").reindex(df.index)
        df["pax_12m"], df["seats_12m"], df["departures_12m"] = t["pax_12m"], t["seats_12m"], t["departures_12m"]
        seats = df["seats_12m"].where(df["seats_12m"] > 0)
        df["load_factor"] = 100.0 * df["pax_12m"] / seats
    if len(prior_months) == T100_WINDOW_MONTHS:
        pred, keys = in_months(prior_months)
        p = _query_df(conn, f"""
            SELECT origin AS iata, SUM(passengers) AS pax_prior_12m, SUM(seats) AS seats_prior_12m
            FROM t100_routes WHERE service_class = ? AND {pred} GROUP BY origin""", [PASSENGER_CLASS, *keys])
        p = p.set_index("iata").reindex(df.index)
        df["pax_prior_12m"], df["seats_prior_12m"] = p["pax_prior_12m"], p["seats_prior_12m"]
    else:
        prior_months = []

    # ── On-Time: flight-weighted delay share, taxi-out, cancel rate, NAS delay ──
    ontime_months = last_months(conn, "ontime_airport_month", ONTIME_WINDOW_MONTHS)
    for col in ("ontime_flights", "delay_share", "taxi_out", "cancel_rate", "nas_delay_min_per_flight"):
        df[col] = float("nan")
    if ontime_months:
        pred, keys = in_months(ontime_months)
        o = _query_df(conn, f"""
            SELECT origin AS iata, SUM(flights) AS ontime_flights,
                   SUM(dep_del15_share * flights) / NULLIF(SUM(flights), 0) AS delay_share,
                   SUM(avg_taxi_out_min * flights) / NULLIF(SUM(flights), 0) AS taxi_out,
                   SUM(cancel_rate * flights) / NULLIF(SUM(flights), 0) AS cancel_rate,
                   SUM(nas_delay_min_per_flight * flights) / NULLIF(SUM(flights), 0) AS nas_delay_min_per_flight
            FROM ontime_airport_month WHERE {pred} GROUP BY origin""", keys)
        o = o.set_index("iata").reindex(df.index)
        df["ontime_flights"] = o["ontime_flights"]
        thin = ~(df["ontime_flights"] >= MIN_ONTIME_DEPARTURES)
        df["delay_share"] = as_percent(o["delay_share"]).mask(thin)
        df["taxi_out"] = o["taxi_out"].astype("float64").mask(thin)
        df["cancel_rate"] = as_percent(o["cancel_rate"]).mask(thin)
        df["nas_delay_min_per_flight"] = o["nas_delay_min_per_flight"].astype("float64").mask(thin)

    # ── TAF: forecast CAGR FY2024 → FY2035 on enplanements_total (incl. international) ──
    df["taf_base"] = df["taf_horizon"] = df["forecast_cagr"] = float("nan")
    if "taf" not in missing:
        f = _query_df(conn, """
            SELECT iata,
                   MAX(CASE WHEN fiscal_year = ? THEN enplanements_total END) AS taf_base,
                   MAX(CASE WHEN fiscal_year = ? THEN enplanements_total END) AS taf_horizon
            FROM taf GROUP BY iata""", [TAF_BASE_FY, TAF_HORIZON_FY]).set_index("iata").reindex(df.index)
        df["taf_base"], df["taf_horizon"] = f["taf_base"].astype("float64"), f["taf_horizon"].astype("float64")
        base = df["taf_base"].where(df["taf_base"] > 0)
        years = TAF_HORIZON_FY - TAF_BASE_FY
        df["forecast_cagr"] = 100.0 * ((df["taf_horizon"] / base) ** (1.0 / years) - 1.0)

    # ── FAA CY enplanements ──
    df["cy2024"] = df["enplanements"] = df["enpl_yoy"] = float("nan")
    if "enplanements" not in missing:
        e = _query_df(conn, "SELECT iata, cy2024, cy2025 FROM enplanements").drop_duplicates("iata")
        e = e.set_index("iata").reindex(df.index)
        df["cy2024"], df["enplanements"] = e["cy2024"].astype("float64"), e["cy2025"].astype("float64")
        df["enpl_yoy"] = 100.0 * (df["enplanements"] / df["cy2024"].where(df["cy2024"] > 0) - 1.0)

    # ── Census CBSA population ──
    df["metro_pop"] = float("nan")
    if "metro_population" not in missing:
        m = _query_df(conn, "SELECT CAST(cbsa_code AS VARCHAR) AS cbsa_code, pop_2025 FROM metro_population")
        pop = m.drop_duplicates("cbsa_code").set_index("cbsa_code")["pop_2025"]
        df["metro_pop"] = df["cbsa_code"].astype("string").map(pop).astype("float64")

    return MetricFrame(df=df, t100_months=t100_months, ontime_months=ontime_months, missing_tables=missing)


def prior_t100_months(conn=None) -> list[tuple[int, int]]:
    conn = conn or get_conn()
    prior = last_months(conn, "t100_routes", T100_WINDOW_MONTHS, offset=T100_WINDOW_MONTHS)
    return prior if len(prior) == T100_WINDOW_MONTHS else []
