"""The Pydantic AI agent: tools are thin wrappers over app.analytics (the LLM never computes)."""

from __future__ import annotations

import os
from typing import Annotated

from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.usage import UsageLimits

from app import analytics
from app.agent.prompt import SYSTEM_PROMPT
from app.contracts import FollowupsData, ResolveData, RouteMixData, ToolResult

DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"
# SPEC §9: at most 12 model requests (tool round-trips) per answer.
USAGE_LIMITS = UsageLimits(request_limit=12)


def model_id() -> str:
    return os.environ.get("MODEL_ID") or DEFAULT_MODEL


agent = Agent(
    model_id(),
    instructions=SYSTEM_PROMPT,
    defer_model_check=True,
    name="airport_analyst",
    model_settings=AnthropicModelSettings(
        anthropic_cache_instructions=True,
        anthropic_cache_tool_definitions=True,
        max_tokens=2048,  # SPEC §9 per-request cap
    ),
)


@agent.tool_plain
def resolve_airports(query: str) -> ToolResult[ResolveData]:
    """Resolve an airport name, city, nickname or code (e.g. "LA", "Santa Ana", "Anchorage", "KSFO")
    to Primary Airport candidates. Returns the best match, alternates and the Assumption made."""
    return analytics.resolve_airports(query)


@agent.tool_plain
def route_mix(iata: str, min_miles: int = 3000, include_cargo: bool = False) -> ToolResult[RouteMixData]:
    """Long-haul share of departures from an airport over the last 12 T-100 months.

    Returns the scheduled-passenger (class F) departures share for segments ≥ min_miles (the
    headline), the passenger-weighted share, the cargo-inclusive share (all classes, a labelled
    variant), ready-made group totals (non-passenger G+L+P and all-cargo G+P long-haul counts and
    shares, so never add class rows yourself), a per-service-class breakdown with each class's
    share of departures and of long-haul departures, and the top long-haul destinations. All three shares
    are always returned; include_cargo only widens the top-destinations list to all service
    classes (leave it false unless the user asks about cargo destinations).
    """
    return analytics.route_mix(iata, min_miles=min_miles, include_cargo=include_cargo)


@agent.tool_plain
def suggest_followups(
    questions: Annotated[list[str], Field(min_length=2, max_length=3)],
) -> FollowupsData:
    """Offer 2–3 short follow-up questions the user can click. Call this as the last tool call of
    every analytic answer, then write the answer text."""
    return FollowupsData(questions=questions)
