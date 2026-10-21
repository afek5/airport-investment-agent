"""The analytics interface (HANDOFF §2). Pure, deterministic functions over the Snapshot.

Every function returns a `ToolResult` envelope (SPEC §5). The LLM never computes: it calls these.
Unknown airports and invalid arguments raise `ValueError` with a message the agent can act on.
"""

from __future__ import annotations

from app.analytics.compare import compare_airports
from app.analytics.query import UnsafeQueryError, query_snapshot
from app.analytics.ranking import airport_scorecard, rank_airports
from app.analytics.resolve import resolve_airports
from app.analytics.route_mix import route_mix
from app.analytics.unmet import unmet_demand

__all__ = [
    "UnsafeQueryError",
    "airport_scorecard",
    "compare_airports",
    "query_snapshot",
    "rank_airports",
    "resolve_airports",
    "route_mix",
    "unmet_demand",
]
