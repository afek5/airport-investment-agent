"""What the model reads of a tool result: large numbers arrive already digit-grouped.

The model copies figures from tool results into its answer. Asked to add thousands separators to a raw
8-digit integer itself, it mis-groups them ("30516426" became "30,516426" in live G4 runs). So, just
before each model request, every number of 10,000 or more inside a tool result is rewritten as its grouped
string ("30,516,426"), and the model copies characters instead of formatting digits.

This changes only the request sent to the model. The stored message history, the Evidence stream to the
frontend and the typed contracts keep the raw numbers. Numbers under 10,000 (years, ranks, miles,
percentages) are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext

GROUP_FROM = 10_000


def grouped(x: Any) -> Any:
    """Deep copy of a JSON-like value with every number ≥ 10,000 in magnitude as a digit-grouped string."""
    if isinstance(x, bool):
        return x
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    if isinstance(x, (int, float)):
        return f"{x:,}" if abs(x) >= GROUP_FROM else x
    if isinstance(x, dict):
        return {k: grouped(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [grouped(v) for v in x]
    return x


def _for_model(part: Any) -> Any:
    if not isinstance(part, ToolReturnPart) or isinstance(part.content, str):
        return part
    content = part.content
    if hasattr(content, "model_dump"):
        content = content.model_dump(mode="json", by_alias=True)
    return replace(part, content=grouped(content))


def for_model(messages: list[ModelMessage]) -> list[ModelMessage]:
    """The messages as the model should read them (new objects; the originals are not modified)."""
    return [replace(m, parts=[_for_model(p) for p in m.parts]) if isinstance(m, ModelRequest) else m
            for m in messages]


@dataclass
class GroupedNumbers(AbstractCapability[Any]):
    """Agent capability: rewrites tool results for the current model request only (see module doc)."""

    async def before_model_request(self, ctx: RunContext[Any], request_context: ModelRequestContext) -> ModelRequestContext:
        request_context.messages = for_model(request_context.messages)
        return request_context
