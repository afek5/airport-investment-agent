"""The Investment Opportunity Score (SPEC §4, ADR 0002). Pure, deterministic functions.

- Percentile Score per metric across the Primary Airports that have it.
- Missing metrics imputed at the median (50), disclosed: the airport's score is Provisional.
- Pillar score = weighted mean of its metric percentiles.
- An airport with no measured metric in a whole Pillar is not ranked.
- Investment Opportunity Score = exp(Σ w_p · ln(max(pillar_p, 1))), range 1–100.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

from app.analytics.common import coverage_level, is_missing
from app.analytics.constants import (
    DEFAULT_WEIGHTS, IMPUTED_PERCENTILE, METRICS, MISSING_REASONS, PILLAR_FLOOR, PILLAR_LABELS, PILLARS,
)
from app.contracts import Weights


def percentile(values: pd.Series) -> pd.Series:
    """Percentile Score 0–100 among the non-null values: rank(pct=True, method="average") * 100."""
    return values.astype("float64").rank(pct=True, method="average") * 100.0


def pillar_metrics(pillar: str) -> list[str]:
    return [k for k, (p, *_rest) in METRICS.items() if p == pillar]


def pillar_score(pillar: str, pcts: Mapping[str, float | None]) -> tuple[float | None, list[str]]:
    """Weighted mean of the Pillar's metric percentiles, missing ones imputed at 50.

    Returns (score, imputed metric keys). The score is None when no metric of the Pillar is measured.
    Example: Capacity Pressure 80/missing/missing → 0.4·80 + 0.3·50 + 0.3·50 = 62.
    """
    keys = pillar_metrics(pillar)
    imputed = [k for k in keys if is_missing(pcts.get(k))]
    if len(imputed) == len(keys):
        return None, imputed
    total_w = sum(METRICS[k][1] for k in keys)
    s = sum(METRICS[k][1] * (IMPUTED_PERCENTILE if k in imputed else float(pcts[k])) for k in keys)
    return s / total_w, imputed


def investment_score(pillars: Mapping[str, float], weights: Weights) -> float:
    """Weighted geometric mean of the Pillars with a floor of 1: exp(Σ w_p · ln(max(p, 1)))."""
    w = weights.normalised()
    return math.exp(sum(getattr(w, p) * math.log(max(pillars[p], PILLAR_FLOOR)) for p in PILLARS))


def as_weights(weights: Weights | Mapping[str, float] | None) -> Weights:
    if weights is None:
        return DEFAULT_WEIGHTS.normalised()
    if isinstance(weights, Weights):
        return weights.normalised()
    merged = {**DEFAULT_WEIGHTS.model_dump(), **{k: float(v) for k, v in weights.items() if v is not None}}
    return Weights(**merged).normalised()


def score_universe(df: pd.DataFrame, weights: Weights) -> pd.DataFrame:
    """Score every universe airport. `df` is indexed by iata and has the seven metric columns
    plus `hub_size`. Returns a frame with pct_<metric>, the three Pillars, score, coverage,
    imputed, missing reasons, not_ranked_reason, national_rank and hub_rank.
    """
    out = pd.DataFrame(index=df.index.copy())
    for k in METRICS:
        out[f"pct_{k}"] = percentile(df[k])

    pillars: dict[str, list] = {p: [] for p in PILLARS}
    imputed_all, measured, not_ranked, scores, reasons = [], [], [], [], []
    for iata in out.index:
        pcts = {k: out.at[iata, f"pct_{k}"] for k in METRICS}
        imputed: list[str] = []
        missing_pillars: list[str] = []
        for p in PILLARS:
            s, imp = pillar_score(p, pcts)
            pillars[p].append(s)
            imputed += imp
            if s is None:
                missing_pillars.append(PILLAR_LABELS[p])
        imputed_all.append(imputed)
        measured.append(len(METRICS) - len(imputed))
        reasons.append(list(dict.fromkeys(MISSING_REASONS[k] for k in imputed)))
        if missing_pillars:
            not_ranked.append("not ranked: insufficient data (no measured metric in "
                              + ", ".join(missing_pillars) + ")")
            scores.append(None)
        else:
            not_ranked.append(None)
            scores.append(investment_score({p: pillars[p][-1] for p in PILLARS}, weights))

    for p in PILLARS:
        out[p] = pd.Series(pillars[p], index=out.index, dtype="float64")
    out["score"] = pd.Series(scores, index=out.index, dtype="float64")
    out["measured"] = measured
    out["imputed"] = imputed_all
    out["missing_reasons"] = reasons
    out["not_ranked_reason"] = pd.Series(not_ranked, index=out.index, dtype=object)
    out["hub_size"] = df["hub_size"]
    out["level"] = [coverage_level(m) for m in measured]
    out["national_rank"] = rank_by(out, "score")
    out["hub_rank"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    for _hub, idx in out[out["score"].notna()].groupby("hub_size").groups.items():
        sub = out.loc[idx]
        out.loc[idx, "hub_rank"] = rank_by(sub, "score")
    return out


def not_ranked_reason(scored: pd.DataFrame, iata: str) -> str | None:
    v = scored.at[iata, "not_ranked_reason"]
    return v if isinstance(v, str) else None


def rank_by(scored: pd.DataFrame, col: str) -> pd.Series:
    """Dense 1..n order by `col` descending, ties broken by IATA code; unranked rows get <NA>.
    Only airports with an overall score are ranked, whatever the column."""
    ok = scored[scored["score"].notna() & scored[col].notna()]
    order = sorted(ok.index, key=lambda i: (-float(ok.at[i, col]), i))
    ranks = pd.Series(pd.NA, index=scored.index, dtype="Int64")
    for n, iata in enumerate(order, start=1):
        ranks[iata] = n
    return ranks
