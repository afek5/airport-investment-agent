"""Scripted FunctionModels for offline tests (no API spend).

- `scripted_model()`: the G3 path: route_mix(ANC) → suggest_followups → an answer quoting the share.
- `text_model(text)`: answers with fixed text and calls no tool.
- `all_tools_model()`: calls every tool (core, then deferred) once, in order, then answers.
- `scope_model()`: answers with the scoping statement when (and only when) the instructions it
  receives carry it, standing in for a compliant LLM on an off-topic request.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

Step = Callable[[list[ModelMessage], AgentInfo], tuple[str, str | dict | list]]


def _tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [p for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]


def _model(step: Step) -> FunctionModel:
    def run(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        kind, payload = step(messages, info)
        if kind == "tool":
            return ModelResponse(parts=[ToolCallPart(payload["name"], payload["args"])])
        if kind == "hidden+tool":  # Sonnet 5.5: text before a tool call returned as an empty thinking block
            return ModelResponse(parts=[ThinkingPart(""), ToolCallPart(payload["name"], payload["args"])])
        if kind == "tools":  # parallel tool calls in one response
            return ModelResponse(parts=[ToolCallPart(c["name"], c["args"]) for c in payload])
        return ModelResponse(parts=[TextPart(payload)])

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        kind, payload = step(messages, info)
        if kind == "tool":
            yield {0: DeltaToolCall(name=payload["name"], json_args=json.dumps(payload["args"]))}
        elif kind == "tools":
            yield {i: DeltaToolCall(name=c["name"], json_args=json.dumps(c["args"])) for i, c in enumerate(payload)}
        else:
            for i, word in enumerate(payload.split(" ")):
                yield word if i == 0 else " " + word

    return FunctionModel(run, stream_function=stream)


def _g3_step(messages: list[ModelMessage], info: AgentInfo) -> tuple[str, str | dict]:
    done = {r.tool_name for r in _tool_returns(messages)}
    if "route_mix" not in done:
        return "tool", {"name": "route_mix", "args": {"iata": "ANC"}}
    if "suggest_followups" not in done:
        return "tool", {"name": "suggest_followups",
                        "args": {"questions": ["Which US airports have the highest long-haul share?",
                                               "How does ANC compare with SEA?"]}}
    rm = next(r for r in _tool_returns(messages) if r.tool_name == "route_mix")
    content = rm.content if isinstance(rm.content, dict) else json.loads(rm.model_response_str())
    share = content["data"]["passenger_departures"]["share_pct"]
    return "text", (f"{share}% of scheduled passenger departures from ANC are Long-haul Flights (≥ 3,000 mi). "
                    "Data Confidence: High.")


def scripted_model() -> FunctionModel:
    return _model(_g3_step)


def text_model(text: str = "OK.") -> FunctionModel:
    return _model(lambda messages, info: ("text", text))


# Every core tool with valid arguments, in the order the all-tools model calls them.
CORE_CALLS: list[tuple[str, dict]] = [
    ("resolve_airports", {"query": "LA"}),
    ("rank_airports", {"states": ["CT", "ME", "MA", "NH", "RI", "VT"]}),
    ("airport_scorecard", {"iata": "BOS"}),
    ("compare_airports", {"iatas": ["LAX", "SNA"], "lens": "congestion"}),
    ("route_mix", {"iata": "ANC"}),
    ("unmet_demand", {"iata": "SFO"}),
    ("live_traffic", {"iata": "SFO", "months": 3}),
    ("od_demand", {"iata": "SFO", "top_n": 3}),
    ("live_delays", {"iatas": ["LAX", "SNA"]}),
    ("query_snapshot", {"sql": "SELECT count(*) AS n FROM airports"}),
    ("suggest_followups", {"questions": ["Why is BOS first?", "What if growth matters twice as much?"]}),
]
# The deferred escape hatches (app.agent.DEFERRED_TOOLS), called after the core tools by the all-tools model.
DEFERRED_CALLS: list[tuple[str, dict]] = [
    ("query_public_api", {"dataset": "dot_airfare_pairs", "select": "year,quarter,avg(fare) AS avg_fare",
                          "where": "airport_1='BOS' AND airport_2='LAX'", "group": "year,quarter", "limit": 8}),
]
ALL_CALLS = CORE_CALLS + DEFERRED_CALLS


ALL_TOOLS_ANSWER = "Done: every core tool answered. Data Confidence: High."


def _all_tools_step(messages: list[ModelMessage], info: AgentInfo) -> tuple[str, str | dict]:
    n = len(_tool_returns(messages))
    if n < len(CORE_CALLS) - 1:
        name, args = CORE_CALLS[n]
        return "tool", {"name": name, "args": args}
    if n < len(ALL_CALLS):  # the last core call and the deferred ones in one parallel step (request_limit 12)
        return "tools", [{"name": name, "args": args} for name, args in ALL_CALLS[n:]]
    return "text", ALL_TOOLS_ANSWER


def all_tools_model() -> FunctionModel:
    return _model(_all_tools_step)


def scope_model(seen: list[str | None]) -> FunctionModel:
    from app.agent.prompt import SCOPING_STATEMENT

    def step(messages: list[ModelMessage], info: AgentInfo) -> tuple[str, str | dict]:
        seen.append(info.instructions)
        if info.instructions and SCOPING_STATEMENT in info.instructions:
            return "text", SCOPING_STATEMENT
        return "text", "Sure, here is a poem about the sea."

    return _model(step)
