"""rank_airports and airport_scorecard over the Investment Opportunity Score (SPEC §4, §5)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import pandas as pd

from app.analytics.common import dedupe, lowest_level, r1
from app.analytics.constants import (
    HUB_SIZE_ALIASES,
    METRICS,
    MIN_ONTIME_DEPARTURES,
    N_METRICS,
    ONTIME_SCOPE_CAVEAT,
    PILLAR_LABELS,
    PILLARS,
    SCREENING_CAVEAT,
    TAF_BASE_FY,
    TAF_HORIZON_FY,
)
from app.analytics.metrics import MetricFrame, load_metrics
from app.analytics.scoring import as_weights, not_ranked_reason, pillar_metrics, rank_by, score_universe
from app.contracts import (
    Coverage,
    DataConfidence,
    MetricRow,
    NotRankedAirport,
    PillarBreakdown,
    PillarScores,
    RankedAirport,
    RankingData,
    ScorecardData,
    ToolResult,
    Weights,
)

PillarArg = Literal["overall", "momentum", "pressure", "scale"]


def scored_universe(weights: Weights) -> tuple[MetricFrame, pd.DataFrame]:
    mf = load_metrics()
    return mf, score_universe(mf.df, weights)


def methodology_assumptions(mf: MetricFrame, weights: Weights, custom: bool) -> list[str]:
    w = weights
    out = [
        (f"Universe: {len(mf.df)} FAA Primary Airports; every metric is a Percentile Score (0–100) among the "
         "Primary Airports that have it."),
        (f"Pillar Weights{' (custom, normalised to sum 1)' if custom else ' (defaults)'}: "
         f"Demand Momentum {w.momentum:.2f}, Capacity Pressure {w.pressure:.2f}, Market Scale {w.scale:.2f}."),
        (f"Demand Momentum = 0.60 × TAF enplanement CAGR FY{TAF_BASE_FY}→FY{TAF_HORIZON_FY} (incl. international) "
         "+ 0.40 × CY2024→CY2025 enplanement growth."),
        (f"Capacity Pressure = 0.40 × class F Load Factor ({mf.t100_window}) + 0.30 × share of departures delayed "
         f"≥15 min + 0.30 × average taxi-out ({mf.ontime_window})."),
        "Market Scale = 0.70 × CY2025 enplanements + 0.30 × 2025 metro (CBSA) population.",
        ("Investment Opportunity Score = weighted geometric mean of the three Pillars (each floored at 1), so "
         "weakness in any one Pillar is penalised."),
        ("Missing metrics are imputed at the median (50th percentile): this pulls the Pillar toward the middle "
         "and can raise or lower an airport; such scores are Provisional and name the imputed metrics."),
        (f"delay_share and taxi_out are left unmeasured for airports with fewer than {MIN_ONTIME_DEPARTURES:,} "
         "reporting-carrier departures in the On-Time window."),
    ]
    if mf.missing_tables:
        out.append("Snapshot tables not available, so their metrics are unmeasured for every airport: "
                   + ", ".join(mf.missing_tables) + ".")
    return out


def _norm_hubs(hub_sizes: list[str] | None) -> list[str] | None:
    if not hub_sizes:
        return None
    out = []
    for h in hub_sizes:
        key = str(h).strip().lower()
        if key not in HUB_SIZE_ALIASES:
            raise ValueError(f"Unknown hub size {h!r}; use L, M, S or N")
        out.append(HUB_SIZE_ALIASES[key])
    return sorted(set(out), key="LMSN".index)


def _scope_label(states, faa_region, hubs) -> str:
    parts = []
    if states:
        parts.append("states " + ", ".join(states))
    if faa_region:
        parts.append(f"FAA region {faa_region}")
    if hubs:
        parts.append("hub sizes " + ", ".join(hubs))
    return "; ".join(parts) + " (Primary Airports)" if parts else "all US Primary Airports"


def _pillar_scores(row) -> PillarScores:
    return PillarScores(**{p: r1(row[p]) for p in PILLARS})


def rank_airports(
    states: list[str] | None = None,
    faa_region: str | None = None,
    hub_sizes: list[str] | None = None,
    pillar: PillarArg = "overall",
    weights: Weights | Mapping[str, float] | None = None,
    top_n: int = 10,
) -> ToolResult[RankingData]:
    """Ranking of Primary Airports by Investment Opportunity Score (or one Pillar) within a scope.

    Percentiles are always national; the scope only filters which airports are listed.
    """
    if pillar not in ("overall", *PILLARS):
        raise ValueError(f"pillar must be overall, momentum, pressure or scale, not {pillar!r}")
    w = as_weights(weights)
    custom = weights is not None
    st = sorted({s.strip().upper() for s in states}) if states else None
    region = faa_region.strip().upper() if faa_region else None
    hubs = _norm_hubs(hub_sizes)
    top_n = max(1, min(int(top_n), 100))

    mf, sc = scored_universe(w)
    df = mf.df
    mask = pd.Series(True, index=df.index)
    if st:
        mask &= df["state"].isin(st)
    if region:
        mask &= df["faa_region"].str.upper() == region
    if hubs:
        mask &= df["hub_size"].isin(hubs)
    scope = sc[mask]

    col = "score" if pillar == "overall" else pillar
    ranks = rank_by(scope, col)
    ranked_idx = sorted((i for i in scope.index if not pd.isna(ranks[i])), key=lambda i: int(ranks[i]))
    shown = ranked_idx[:top_n]
    ranked = [
        RankedAirport(
            rank=int(ranks[i]), iata=i, name=df.at[i, "name"], state=df.at[i, "state"],
            hub_size=df.at[i, "hub_size"], score=r1(sc.at[i, col]), pillars=_pillar_scores(sc.loc[i]),
            coverage=Coverage(measured=int(sc.at[i, "measured"]), of=N_METRICS),
            provisional=int(sc.at[i, "measured"]) < N_METRICS, imputed_metrics=list(sc.at[i, "imputed"]),
        )
        for i in shown
    ]
    not_ranked = [
        NotRankedAirport(iata=i, name=df.at[i, "name"], reason=not_ranked_reason(sc, i))
        for i in scope.index if not_ranked_reason(sc, i)
    ]
    data = RankingData(
        scope=_scope_label(st, region, hubs), states=st, faa_region=region, hub_sizes=hubs, pillar=pillar,
        weights=w, universe_size=len(df), ranked=ranked, not_ranked=not_ranked,
    )

    # Data Confidence: the weakest listed airport sets the level (SPEC §6: the lowest level wins).
    levels = [sc.at[i, "level"] for i in shown]
    provisional = [r for r in ranked if r.provisional]
    reasons = [(f"{len(ranked) - len(provisional)} of {len(ranked)} listed airports have full Coverage "
                f"({N_METRICS}/{N_METRICS}).")] if ranked else []
    if provisional:
        reasons.append("Provisional: " + "; ".join(
            f"{r.iata} {r.coverage.measured}/{N_METRICS} (imputed {', '.join(r.imputed_metrics)})" for r in provisional))
    reasons += dedupe([reason for i in shown for reason in sc.at[i, "missing_reasons"]])
    if not ranked:
        reasons.append("no airport in this scope has enough data to be ranked" if len(scope)
                       else "no Primary Airport matches this scope")

    caveats = [SCREENING_CAVEAT, ONTIME_SCOPE_CAVEAT]
    if pillar != "overall":
        caveats.append(f"Ranked by the {PILLAR_LABELS[pillar]} Pillar alone, not by the Investment "
                       "Opportunity Score.")
    if not_ranked:
        caveats.append(f"{len(not_ranked)} airport(s) in scope are not ranked: insufficient data "
                       f"({', '.join(n.iata for n in not_ranked)}).")
    if len(ranked_idx) > top_n:
        caveats.append(f"Showing the top {top_n} of {len(ranked_idx)} ranked airports in scope.")
    return ToolResult[RankingData](
        data=data,
        sources=mf.score_sources(),
        assumptions=methodology_assumptions(mf, w, custom),
        data_confidence=DataConfidence(level=lowest_level(levels) if ranked else "Low", reasons=reasons),
        caveats=caveats,
    )


def airport_scorecard(iata: str, weights: Weights | Mapping[str, float] | None = None) -> ToolResult[ScorecardData]:
    """Full breakdown of one airport's Investment Opportunity Score: raw value, percentile, Pillar,
    national rank, rank within hub size and Coverage."""
    code = iata.strip().upper()
    w = as_weights(weights)
    mf, sc = scored_universe(w)
    df = mf.df
    if code not in df.index:
        raise ValueError(f"{code} is not a Primary Airport in the Snapshot; use resolve_airports first")
    row, s = df.loc[code], sc.loc[code]
    pillars = []
    for p in PILLARS:
        rows = [
            MetricRow(metric=k, label=METRICS[k][2], pillar=p, raw_value=r1(row[k]), unit=METRICS[k][3],
                      percentile=r1(s[f"pct_{k}"]), imputed=k in s["imputed"], weight_in_pillar=METRICS[k][1])
            for k in pillar_metrics(p)
        ]
        pillars.append(PillarBreakdown(pillar=p, score=r1(s[p]), weight=round(getattr(w, p), 4), metrics=rows))
    measured = int(s["measured"])
    hub = row["hub_size"]
    ranked = sc["score"].notna()
    data = ScorecardData(
        iata=code, name=row["name"], state=row["state"], hub_size=hub, weights=w, score=r1(s["score"]),
        provisional=measured < N_METRICS, not_ranked_reason=not_ranked_reason(sc, code),
        national_rank=None if pd.isna(s["national_rank"]) else int(s["national_rank"]),
        national_of=int(ranked.sum()),
        hub_rank=None if pd.isna(s["hub_rank"]) else int(s["hub_rank"]),
        hub_of=int((ranked & (sc["hub_size"] == hub)).sum()),
        pillars=pillars, imputed_metrics=list(s["imputed"]),
    )
    reasons = [f"Coverage {measured}/{N_METRICS} measured metrics."] + list(s["missing_reasons"])
    caveats = [SCREENING_CAVEAT, ONTIME_SCOPE_CAVEAT]
    if data.provisional and data.score is not None:
        caveats.append(f"Provisional Score: {', '.join(data.imputed_metrics)} imputed at the median (50).")
    if data.not_ranked_reason:
        caveats.append(f"{code} is {data.not_ranked_reason}.")
    return ToolResult[ScorecardData](
        data=data,
        sources=mf.score_sources(),
        assumptions=methodology_assumptions(mf, w, weights is not None),
        data_confidence=DataConfidence(level=s["level"], reasons=reasons),
        coverage=Coverage(measured=measured, of=N_METRICS),
        caveats=caveats,
    )
