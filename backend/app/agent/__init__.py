"""The Pydantic AI agent: tools are thin wrappers over app.analytics and app.live (the LLM never computes).

Core tools (SPEC §5): resolve_airports, rank_airports, airport_scorecard, compare_airports, route_mix,
unmet_demand, live_traffic, od_demand, live_delays, query_snapshot, suggest_followups.
Deferred (P4): query_public_api, a guarded live SoQL escape hatch over three whitelisted public datasets.
The agent has no web, shell or write tools; query_snapshot is read-only DuckDB.
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.usage import UsageLimits

from app import analytics, live
from app.agent.display import GroupedNumbers
from app.agent.prompt import SYSTEM_PROMPT
from app.contracts import (
    AdHocData, ComparisonData, FollowupsData, LiveDelaysData, LiveTrafficData, OdDemandData, PublicApiData,
    RankingData, ResolveData, RouteMixData, ScorecardData, ToolResult, UnmetDemandData, Weights,
)

log = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"
# SPEC §9: at most 12 model requests (tool round-trips) per answer.
USAGE_LIMITS = UsageLimits(request_limit=12)
MAX_TOKENS = 2048  # SPEC §9 per-request cap

CORE_TOOLS = (
    "resolve_airports", "rank_airports", "airport_scorecard", "compare_airports", "route_mix", "unmet_demand",
    "live_traffic", "od_demand", "live_delays", "query_snapshot", "suggest_followups",
)
# Deferred escape hatches registered after the core (HANDOFF P4); ALL_TOOLS is everything the agent can call.
DEFERRED_TOOLS = ("query_public_api",)
ALL_TOOLS = CORE_TOOLS + DEFERRED_TOOLS

Iata = Annotated[str, Field(description="3-letter IATA airport code, e.g. 'SFO'", min_length=3, max_length=4)]
State = Annotated[str, Field(description="2-letter US state code, e.g. 'MA'", min_length=2, max_length=2)]
HubSize = Literal["L", "M", "S", "N"]


class ToolError(BaseModel):
    """Returned instead of an envelope when a tool fails unexpectedly; the agent says so and moves on."""

    error: str
    tool: str


def model_id() -> str:
    return os.environ.get("MODEL_ID") or DEFAULT_MODEL


agent = Agent(
    model_id(),
    instructions=SYSTEM_PROMPT,
    defer_model_check=True,
    name="airport_analyst",
    retries=2,
    # The model reads large numbers already digit-grouped, so it copies them instead of formatting them.
    capabilities=[GroupedNumbers()],
    model_settings=AnthropicModelSettings(
        anthropic_cache_instructions=True,
        anthropic_cache_tool_definitions=True,
        max_tokens=MAX_TOKENS,
    ),
)


def _guarded(fn):
    """Bad arguments (unknown airport, invalid SQL, bad weights) go back to the model as a retry prompt;
    anything else becomes a ToolError result instead of crashing the answer."""

    def handle(e: Exception) -> ToolError:
        if isinstance(e, (ValueError, LookupError)):
            raise ModelRetry(f"{fn.__name__}: {e}") from e
        log.exception("tool %s failed", fn.__name__)
        return ToolError(tool=fn.__name__, error=f"{type(e).__name__}: {e}")

    if _is_async(fn):
        @functools.wraps(fn)
        async def run_async(*args: Any, **kwargs: Any):
            try:
                return await fn(*args, **kwargs)
            except ModelRetry:
                raise
            except Exception as e:  # noqa: BLE001
                return handle(e)
        return run_async

    @functools.wraps(fn)
    def run(*args: Any, **kwargs: Any):
        try:
            return fn(*args, **kwargs)
        except ModelRetry:
            raise
        except Exception as e:  # noqa: BLE001
            return handle(e)
    return run


def _is_async(fn) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn)


# ───────────────────────────── Snapshot tools (deterministic) ─────────────────────────────


@agent.tool_plain
@_guarded
def resolve_airports(query: str) -> ToolResult[ResolveData] | ToolError:
    """Resolve an airport name, city, nickname or code (e.g. "LA", "Santa Ana", "Anchorage", "KSFO")
    to Primary Airport candidates. Returns the best match, alternates and the Assumption made."""
    return analytics.resolve_airports(query)


@agent.tool_plain
@_guarded
def rank_airports(
    states: list[State] | None = None,
    faa_region: str | None = None,
    hub_sizes: list[HubSize] | None = None,
    pillar: Literal["overall", "momentum", "pressure", "scale"] = "overall",
    weights: Weights | None = None,
    top_n: Annotated[int, Field(ge=1, le=50)] = 10,
) -> ToolResult[RankingData] | ToolError:
    """Ranking of Primary Airports by Investment Opportunity Score (or one Pillar) within a scope.

    Scope by `states` (2-letter codes; map region names yourself, e.g. New England = CT, ME, MA, NH, RI, VT),
    `faa_region` (FAA region code such as 'NE', 'WP', 'AL') and/or `hub_sizes` (L large, M medium, S small,
    N nonhub). `weights` overrides the Pillar Weights (momentum, pressure, scale; normalised to sum 1), e.g.
    "growth matters twice as much" → momentum doubled relative to the defaults 0.35/0.40/0.25.
    Returns ranked airports with Pillar scores, Coverage, Provisional marks, the not-ranked list and the
    screening caveat.
    """
    return analytics.rank_airports(states=states, faa_region=faa_region, hub_sizes=hub_sizes, pillar=pillar,
                                   weights=weights, top_n=top_n)


@agent.tool_plain
@_guarded
def airport_scorecard(iata: Iata, weights: Weights | None = None) -> ToolResult[ScorecardData] | ToolError:
    """Full Investment Opportunity Score breakdown for one airport: each metric's raw value, Percentile Score
    and whether it was imputed, each Pillar score, the national rank and the rank within its Hub Size."""
    return analytics.airport_scorecard(iata.upper(), weights=weights)


@agent.tool_plain
@_guarded
def compare_airports(
    iatas: Annotated[list[Iata], Field(min_length=2, max_length=6)],
    lens: Literal["congestion", "demand", "scorecard"] = "congestion",
) -> ToolResult[ComparisonData] | ToolError:
    """Compare 2–6 airports side by side through one lens.

    - congestion: delay share, taxi-out, cancellations, NAS-delay minutes per flight, monthly departures,
      departures per runway per day and load factor, each with its national percentile, plus a
      congestion_index (a lens, not the Investment Opportunity Score).
    - demand: Demand Momentum and Market Scale metrics.
    - scorecard: Investment Opportunity Score and Pillars.
    """
    return analytics.compare_airports([c.upper() for c in iatas], lens=lens)


@agent.tool_plain
@_guarded
def route_mix(iata: Iata, min_miles: int = 3000, include_cargo: bool = False) -> ToolResult[RouteMixData] | ToolError:
    """Long-haul share of departures from an airport over the last 12 T-100 months.

    Returns the scheduled-passenger (class F) departures share for segments ≥ min_miles (the
    headline), the passenger-weighted share, the cargo-inclusive share (all classes, a labelled
    variant), ready-made group totals (non-passenger G+L+P and all-cargo G+P long-haul counts and
    shares, so never add class rows yourself), a per-service-class breakdown with each class's
    share of departures and of long-haul departures, and the top long-haul destinations. All three shares
    are always returned; include_cargo only widens the top-destinations list to all service
    classes (leave it false unless the user asks about cargo destinations).
    """
    return analytics.route_mix(iata.upper(), min_miles=min_miles, include_cargo=include_cargo)


@agent.tool_plain
@_guarded
def unmet_demand(iata: Iata) -> ToolResult[UnmetDemandData] | ToolError:
    """Unmet Demand at one airport: observed Constraint Evidence first (delay share and taxi-out vs the
    national median, NAS-delay minutes, the IFR vs VFR runway-capacity drop where known, high-load-factor
    route-months, seat vs passenger growth), then the Forecast Gap (FAA TAF FY2024 → FY2030), then a
    separately labelled Spill Scenario (assumed spill rates, not calibrated), the fixed `cannot_determine`
    list and deterministic `why_drivers` ordered by strength."""
    return analytics.unmet_demand(iata.upper())


@agent.tool_plain
@_guarded
def query_snapshot(sql: str) -> ToolResult[AdHocData] | ToolError:
    """Escape hatch: one read-only SELECT/WITH query over the Snapshot views (data dictionary in the
    instructions). 200-row cap, 5 s timeout. The result is ad hoc (Data Confidence at most Medium) and the
    SQL is shown to the user. Prefer the dedicated tools whenever one fits."""
    return analytics.query_snapshot(sql)


# ───────────────────────────── Live Signals ─────────────────────────────


@agent.tool_plain
@_guarded
async def live_traffic(iata: Iata, months: Annotated[int, Field(ge=1, le=36)] = 12) -> ToolResult[LiveTrafficData] | ToolError:
    """LIVE (BTS SODA): the latest monthly departures, passengers, seats and load factor for an airport,
    all carriers. A Live Signal for context; it never changes a score."""
    return await live.live_traffic(iata, months=months)


@agent.tool_plain
@_guarded
async def od_demand(iata: Iata, top_n: Annotated[int, Field(ge=1, le=25)] = 10) -> ToolResult[OdDemandData] | ToolError:
    """LIVE (DOT Consumer Airfare Report, latest quarter): the airport's largest domestic O&D markets with
    passengers per day, average fare, the largest carrier and its share, and the low-fare carrier. Use it
    with unmet_demand for the demand side of the story (fares and carrier concentration)."""
    return await live.od_demand(iata, top_n=top_n)


@agent.tool_plain
@_guarded
async def live_delays(iatas: list[Iata] | None = None) -> ToolResult[LiveDelaysData] | ToolError:
    """LIVE (FAA NAS Status): current ground stops, ground delay programs, arrival/departure delays and
    closures. Pass the airports you care about; `no_active_delay` lists the ones with nothing active now."""
    return await live.live_delays(iatas)


@agent.tool_plain
@_guarded
async def query_public_api(
    dataset: Literal["bts_airport_month", "dot_airfare_pairs", "dot_airfare_city_pairs"],
    select: str | None = None,
    where: str | None = None,
    group: str | None = None,
    order: str | None = None,
    limit: Annotated[int, Field(ge=1, le=500)] = 100,
) -> ToolResult[PublicApiData] | ToolError:
    """LIVE escape hatch: one SoQL query on a whitelisted public dataset, only when no other tool answers
    (e.g. fare history for one market by quarter). Pass clause bodies only, no `$` or `&`:
    select="year,quarter,avg(fare) AS avg_fare", where="airport_1='BOS' AND airport_2='LAX'",
    group="year,quarter", order="year DESC,quarter DESC". Aggregate in SoQL so the result holds the figure you
    quote. Result is ad hoc (Data Confidence at most Medium) and the query is shown to the user.

    - bts_airport_month (BTS r495-tyji, one row per origin airport × month, all carriers): origin_airport_code,
      origin_airport_name, year (text), reporting_month (date, e.g. '2026-04-01T00:00:00.000'),
      total_departures, total_passengers, total_seats, total_load_factor (%), total_freight_lbs,
      domestic_departures, domestic_passengers, domestic_seats, domestic_load_factor.
    - dot_airfare_pairs (DOT Consumer Airfare Report Table 1a, airport-pair markets × quarter): year, quarter,
      airport_1, airport_2 (either order, so match both), city1, city2, nsmiles, passengers (per day),
      fare (average one-way $), carrier_lg, large_ms (share 0–1), fare_lg, carrier_low, lf_ms, fare_low.
    - dot_airfare_city_pairs (Table 6, city-pair markets of 10+ passengers a day × quarter): the same
      columns without airport codes; city1/city2 look like 'Boston, MA (Metropolitan Area)'.
    """
    return await live.query_public_api(dataset, select=select, where=where, group=group, order=order, limit=limit)


# ───────────────────────────── UI ─────────────────────────────


@agent.tool_plain
def suggest_followups(
    questions: Annotated[list[str], Field(min_length=2, max_length=3)],
) -> FollowupsData:
    """Offer 2–3 short follow-up questions the user can click. Call this as the last tool call of
    every analytic answer, then write the answer text."""
    return FollowupsData(questions=questions)
