"""What the model reads of a tool result: counts and amounts arrive already digit-grouped.

The model copies figures from tool results into its answer. Asked to add thousands separators to a raw
integer itself, it mis-groups them ("30516426" became "30,516426" in live G4 runs) or leaves them bare
("1005" class F long-haul departures at ANC next to "37,243"). So, just before each model request, every
number of 1,000 or more inside a tool result is rewritten as its grouped string ("1,005", "30,516,426"),
and the model copies characters instead of formatting digits.

Period labels and identifiers are not quantities and stay as they are: a value whose key names a year,
fiscal year, quarter, month, period, rank, id or code (`year`, `from_fy`, `reporting_month`, `national_rank`,
`airport_id`, `cbsa_code`…) is never grouped, whatever its size. Ad-hoc tables (`columns` + `rows`) use
the column name as the key. The choice is made by key name only, never by value range.

This changes only the request sent to the model. The stored message history, the Evidence stream to the
frontend and the typed contracts keep the raw numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext

GROUP_FROM = 1_000

# The last `_`-separated token of a key that names a label, not a quantity: `from_fy`, `reporting_month`,
# `national_rank`, `origin_airport_id`, `cbsa_code`. A count of labels keeps its own last token
# (`months_over_threshold`, `period_count`) and is grouped like any other count.
LABEL_TOKENS = frozenset({
    "year", "yr", "fy", "cy", "fiscal", "quarter", "qtr", "month", "period", "ym", "yyyymm", "date",
    "rank", "id", "ids", "code", "codes", "iata", "icao", "faa", "fips", "zip", "seq", "pk", "tbl", "cbsa",
})
# Whole keys holding lists of labels.
LABEL_KEYS = frozenset({"years", "fys", "quarters", "months", "periods", "ranks"})


def is_label_key(key: Any) -> bool:
    """True when the key names a period label, a rank, an id or a code (its values are never grouped)."""
    if not isinstance(key, str) or not key:
        return False
    k = key.strip().lower()
    return k in LABEL_KEYS or k.replace("-", "_").split("_")[-1] in LABEL_TOKENS


def grouped(x: Any, label: bool = False) -> Any:
    """Deep copy of a JSON-like value with every number ≥ 1,000 in magnitude as a digit-grouped string,
    except values under a label key (see `is_label_key`)."""
    if isinstance(x, bool):
        return x
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    if isinstance(x, (int, float)):
        return f"{x:,}" if abs(x) >= GROUP_FROM and not label else x
    if isinstance(x, dict):
        cols = x.get("columns")
        if isinstance(cols, list) and isinstance(x.get("rows"), list):
            labels = [is_label_key(c) for c in cols]
            rows = [[grouped(v, labels[i] if i < len(labels) else False) for i, v in enumerate(r)]
                    if isinstance(r, list) else grouped(r) for r in x["rows"]]
            return {k: rows if k == "rows" else grouped(v, label or is_label_key(k)) for k, v in x.items()}
        return {k: grouped(v, label or is_label_key(k)) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [grouped(v, label) for v in x]
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
