"""compare_airports: side-by-side lenses (SPEC §4 "Congestion lens", §5)."""

from __future__ import annotations

from typing import Literal

import pandas as pd

from app.analytics.common import is_missing, r1
from app.analytics.constants import (
    CONGESTION_INDEX_METRICS,
    METRICS,
    MIN_ONTIME_DEPARTURES,
    N_METRICS,
    ONTIME_SCOPE_CAVEAT,
    PILLAR_LABELS,
    PILLARS,
    SCREENING_CAVEAT,
    T100_WINDOW_MONTHS,
)
from app.analytics.metrics import MetricFrame, load_metrics
from app.analytics.scoring import as_weights, percentile, score_universe
from app.contracts import ComparisonData, ComparisonMetric, DataConfidence, ToolResult

Lens = Literal["congestion", "demand", "scorecard"]

# key → (label, unit, has a national percentile)
CONGESTION_ROWS = {
    "delay_share": ("Departures delayed ≥15 min", "%", True),
    "taxi_out": ("Average taxi-out", "min", True),
    "cancel_rate": ("Cancelled departures", "%", True),
    "nas_delay_min_per_flight": ("NAS (airspace/airport) delay per departure", "min", True),
    "monthly_departures": ("Departures per month, all T-100 service classes", "departures", True),
    "deps_per_runway_day": ("Departures per runway per day", "departures", True),
    "load_factor": ("Load Factor, scheduled passenger flights (class F)", "%", True),
    "ontime_flights": ("Reporting-carrier departures in the On-Time window", "departures", False),
    "runway_count": ("Runways", "runways", False),
}
DEMAND_ROWS = {
    "enplanements": ("Enplanements, CY2025", "passengers", True),
    "enpl_yoy": ("Enplanement growth, CY2024→CY2025", "%", True),
    "forecast_cagr": ("FAA TAF forecast enplanement CAGR, FY2024→FY2035", "% / yr", True),
    "metro_pop": ("Metro (CBSA) population, 2025", "people", True),
    "pax_12m": ("Passengers, class F, last 12 T-100 months", "passengers", True),
    "pax_growth_pct": ("Passenger growth, last 12 vs prior 12 T-100 months", "%", True),
    "load_factor": ("Load Factor, scheduled passenger flights (class F)", "%", True),
}


def derived_columns(mf: MetricFrame) -> pd.DataFrame:
    """Add the congestion and demand fields that are not score metrics."""
    df = mf.df.copy()
    n = len(mf.t100_months) or T100_WINDOW_MONTHS
    df["monthly_departures"] = df["departures_12m"] / n
    days = 365.25 * n / 12
    runways = df["runway_count"].astype("float64").where(df["runway_count"] > 0)
    df["deps_per_runway_day"] = df["departures_12m"] / days / runways
    prior = df["pax_prior_12m"].where(df["pax_prior_12m"] > 0)
    df["pax_growth_pct"] = 100.0 * (df["pax_12m"] / prior - 1.0)
    seats_prior = df["seats_prior_12m"].where(df["seats_prior_12m"] > 0)
    df["seat_growth_pct"] = 100.0 * (df["seats_12m"] / seats_prior - 1.0)
    return df


def _rows(df: pd.DataFrame, codes: list[str], spec: dict) -> list[ComparisonMetric]:
    out = []
    for key, (label, unit, with_pct) in spec.items():
        col = df[key].astype("float64")
        pct = percentile(col) if with_pct else None
        out.append(ComparisonMetric(
            key=key, label=label, unit=unit,
            values={c: r1(col[c]) for c in codes},
            percentiles={c: r1(pct[c]) for c in codes} if with_pct else {},
        ))
    return out


def compare_airports(iatas: list[str], lens: Lens = "congestion") -> ToolResult[ComparisonData]:
    """Compare 2–6 Primary Airports side by side through one lens: congestion (On-Time delays,
    taxi-out, cancellations, NAS delay, departures per runway, Load Factor), demand, or scorecard."""
    codes = list(dict.fromkeys(c.strip().upper() for c in iatas))
    if not 2 <= len(codes) <= 6:
        raise ValueError("compare_airports takes 2 to 6 distinct airports")
    if lens not in ("congestion", "demand", "scorecard"):
        raise ValueError(f"lens must be congestion, demand or scorecard, not {lens!r}")
    mf = load_metrics()
    unknown = [c for c in codes if c not in mf.df.index]
    if unknown:
        raise ValueError(f"Not Primary Airports in the Snapshot: {', '.join(unknown)}; use resolve_airports first")
    df = derived_columns(mf)
    names = {c: df.at[c, "name"] for c in codes}
    assumptions: list[str] = ["National percentiles are among the FAA Primary Airports that have each metric."]
    caveats: list[str] = []
    congestion_index = None
    sources = mf.score_sources()

    if lens == "congestion":
        metrics = _rows(df, codes, CONGESTION_ROWS)
        pcts = {m.key: m.percentiles for m in metrics}
        congestion_index = {}
        for c in codes:
            vals = [pcts[k][c] for k in CONGESTION_INDEX_METRICS]
            congestion_index[c] = None if any(is_missing(v) for v in vals) else r1(sum(vals) / len(vals))
        assumptions += [
            (f"On-Time metrics ({mf.ontime_window}) are flight-weighted over the reporting carriers' departures; "
             f"they are left unmeasured below {MIN_ONTIME_DEPARTURES:,} departures."),
            (f"Departures per month and per runway per day use all T-100 service classes ({mf.t100_window}) and "
             "the OurAirports runway count."),
            ("congestion_index = mean national percentile of delay share, taxi-out and NAS delay per departure; "
             "it is a congestion lens, not the Investment Opportunity Score."),
            "Current NAS status is a Live Signal from the live_delays tool and is not part of this comparison.",
        ]
        caveats.append(ONTIME_SCOPE_CAVEAT)
        if any(v is None for v in congestion_index.values()):
            caveats.append("congestion_index is not computed for airports missing any of its three metrics.")
    elif lens == "demand":
        metrics = _rows(df, codes, DEMAND_ROWS)
        assumptions.append("Passenger growth compares the last 12 with the prior 12 T-100 months (class F); "
                           "it is unmeasured when the Snapshot has fewer than 24 months.")
    else:
        w = as_weights(None)
        sc = score_universe(mf.df, w)
        ranked = sc["score"].notna()
        metrics = [ComparisonMetric(key="score", label="Investment Opportunity Score", unit="1–100",
                                    values={c: r1(sc.at[c, "score"]) for c in codes})]
        metrics += [ComparisonMetric(key=p, label=PILLAR_LABELS[p], unit="0–100",
                                     values={c: r1(sc.at[c, p]) for c in codes}) for p in PILLARS]
        metrics.append(ComparisonMetric(key="coverage_measured", label=f"Coverage (measured of {N_METRICS})",
                                        unit=f"of {N_METRICS}",
                                        values={c: float(sc.at[c, "measured"]) for c in codes}))
        metrics.append(ComparisonMetric(
            key="national_rank", label=f"National rank (of {int(ranked.sum())} ranked)", unit="rank",
            values={c: None if pd.isna(sc.at[c, "national_rank"]) else float(sc.at[c, "national_rank"])
                    for c in codes}))
        metrics += _rows(mf.df, codes, {k: (METRICS[k][2], METRICS[k][3], True) for k in METRICS})
        assumptions.append("Scores use the default Pillar Weights; use airport_scorecard for custom weights.")
        caveats.append(SCREENING_CAVEAT)
        prov = [c for c in codes if int(sc.at[c, "measured"]) < N_METRICS]
        if prov:
            caveats.append("Provisional Scores (median-imputed metrics): " + "; ".join(
                f"{c} imputed {', '.join(sc.at[c, 'imputed'])}" for c in prov))

    cells = [m.values[c] for m in metrics for c in codes]
    missing = sum(1 for v in cells if is_missing(v))
    if missing == 0:
        level, reasons = "High", ["every compared metric is measured for every airport"]
    elif missing * 3 <= len(cells):
        level, reasons = "Medium", [f"{missing} of {len(cells)} compared values are unmeasured"]
    else:
        level, reasons = "Low", [f"{missing} of {len(cells)} compared values are unmeasured"]
    for m in metrics:
        gaps = [c for c in codes if is_missing(m.values[c])]
        if gaps:
            reasons.append(f"{m.label}: unmeasured for {', '.join(gaps)}")
    return ToolResult[ComparisonData](
        data=ComparisonData(lens=lens, iatas=codes, names=names, metrics=metrics, congestion_index=congestion_index),
        sources=sources,
        assumptions=assumptions,
        data_confidence=DataConfidence(level=level, reasons=reasons),
        caveats=caveats,
    )
