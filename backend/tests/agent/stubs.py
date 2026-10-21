"""Stand-ins for the analytics and live functions, so wiring tests don't depend on P1-B data or the network.

Each stub returns a valid `ToolResult` envelope for its tool and records the arguments it received.
"""

from __future__ import annotations

from typing import Any

import pytest

from app import analytics, live
from app.contracts import (
    AdHocData, ComparisonData, DataConfidence, LiveDelaysData, LiveTrafficData, OdDemandData, PublicApiData,
    RankingData,
    ScorecardData, Source, ToolResult, UnmetDemandData, Weights,
)

SRC = [Source(name="stub", url="https://example.invalid", as_of="Jul 2026")]
HIGH = DataConfidence(level="High", reasons=["stub"])


def _env(data: Any, **kw: Any) -> ToolResult:
    return ToolResult[type(data)](data=data, sources=SRC, data_confidence=kw.pop("dc", HIGH), **kw)


def stub_core_tools(monkeypatch: pytest.MonkeyPatch, stub_snapshot_tools: bool = True) -> dict[str, list]:
    calls: dict[str, list] = {}

    def rec(name: str, result):
        def fn(*args: Any, **kwargs: Any):
            calls.setdefault(name, []).append((args, kwargs))
            return result(*args, **kwargs)
        return fn

    def arec(name: str, result):
        async def fn(*args: Any, **kwargs: Any):
            calls.setdefault(name, []).append((args, kwargs))
            return result(*args, **kwargs)
        return fn

    def ranking(**kw: Any):
        return _env(RankingData(scope="stub scope", states=kw.get("states"), weights=kw.get("weights") or Weights(),
                                universe_size=0, ranked=[]),
                    caveats=["screening signal; does not establish renovation profitability"])

    def scorecard(iata: str, weights: Weights | None = None):
        return _env(ScorecardData(iata=iata, name="Stub", state="MA", hub_size="L", weights=weights or Weights(),
                                  score=50.0, provisional=False, national_rank=1, national_of=1, hub_rank=1,
                                  hub_of=1, pillars=[]))

    def comparison(iatas: list[str], lens: str = "congestion"):
        return _env(ComparisonData(lens=lens, iatas=iatas, names={i: i for i in iatas}, metrics=[]))

    def unmet(iata: str):
        return _env(UnmetDemandData(iata=iata, name="Stub", constraint_evidence=[], forecast_gap=None,
                                    spill_scenario=None, cannot_determine=["actual denied passengers"],
                                    why_drivers=[]), dc=DataConfidence(level="Medium", reasons=["stub"]))

    def adhoc(sql: str):
        return _env(AdHocData(sql=sql, columns=["n"], rows=[[1]], row_count=1, truncated=False), ad_hoc=True,
                    dc=DataConfidence(level="Medium", reasons=["ad hoc"]))

    if stub_snapshot_tools:
        monkeypatch.setattr(analytics, "rank_airports", rec("rank_airports", ranking))
        monkeypatch.setattr(analytics, "airport_scorecard", rec("airport_scorecard", scorecard))
        monkeypatch.setattr(analytics, "compare_airports", rec("compare_airports", comparison))
        monkeypatch.setattr(analytics, "unmet_demand", rec("unmet_demand", unmet))
        monkeypatch.setattr(analytics, "query_snapshot", rec("query_snapshot", adhoc))
    monkeypatch.setattr(live, "live_traffic", arec("live_traffic", lambda iata, months=12: _env(
        LiveTrafficData(iata=iata, months=[]))))
    monkeypatch.setattr(live, "od_demand", arec("od_demand", lambda iata, top_n=10: _env(
        OdDemandData(iata=iata, year=2026, quarter=1, markets=[]))))
    monkeypatch.setattr(live, "live_delays", arec("live_delays", lambda iatas=None: _env(
        LiveDelaysData(update_time="now", queried=iatas or [], delays=[], no_active_delay=iatas or []))))
    monkeypatch.setattr(live, "query_public_api", arec("query_public_api", lambda dataset, limit=100, **kw: _env(
        PublicApiData(sql="$select=year", columns=["year"], rows=[[2026]], row_count=1, truncated=False,
                      dataset=dataset, resource_id="tfrh-tu9e", endpoint="https://example.invalid", limit=limit),
        ad_hoc=True, dc=DataConfidence(level="Medium", reasons=["ad hoc"]))))
    return calls
