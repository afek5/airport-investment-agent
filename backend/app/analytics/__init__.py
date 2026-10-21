"""The analytics interface (HANDOFF §2). Pure, deterministic functions over the Snapshot.

Every function returns a `ToolResult` envelope. P0 implements `route_mix` and
`resolve_airports`; P1-B implements the rest behind these exact signatures.
"""

from __future__ import annotations

from typing import Literal

from app.analytics.resolve import resolve_airports
from app.analytics.route_mix import route_mix
from app.contracts import (
    AdHocData, ComparisonData, RankingData, ScorecardData, ToolResult, UnmetDemandData, Weights,
)

__all__ = [
    "resolve_airports", "route_mix", "rank_airports", "airport_scorecard", "compare_airports",
    "unmet_demand", "query_snapshot",
]


def rank_airports(
    states: list[str] | None = None,
    faa_region: str | None = None,
    hub_sizes: list[str] | None = None,
    pillar: Literal["overall", "momentum", "pressure", "scale"] = "overall",
    weights: Weights | None = None,
    top_n: int = 10,
) -> ToolResult[RankingData]:
    raise NotImplementedError("P1-B")


def airport_scorecard(iata: str, weights: Weights | None = None) -> ToolResult[ScorecardData]:
    raise NotImplementedError("P1-B")


def compare_airports(
    iatas: list[str], lens: Literal["congestion", "demand", "scorecard"] = "congestion"
) -> ToolResult[ComparisonData]:
    raise NotImplementedError("P1-B")


def unmet_demand(iata: str) -> ToolResult[UnmetDemandData]:
    raise NotImplementedError("P1-B")


def query_snapshot(sql: str) -> ToolResult[AdHocData]:
    raise NotImplementedError("P1-B")
