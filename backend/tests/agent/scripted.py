"""Scripted FunctionModels for offline tests (no API spend).

- `scripted_model()`: the G3 path: route_mix(ANC) → suggest_followups → an answer quoting the share.
- `text_model(text)`: answers with fixed text and calls no tool.
- `all_tools_model()`: calls every core tool once, in order, then answers.
- `scope_model()`: answers with the scoping statement when (and only when) the instructions it
  receives carry it, standing in for a compliant LLM on an off-topic request.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

Step = Callable[[list[ModelMessage], AgentInfo], tuple[str, str | dict]]


def _tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [p for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]


def _model(step: Step) -> FunctionModel:
    def run(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        kind, payload = step(messages, info)
        if kind == "tool":
            return ModelResponse(parts=[ToolCallPart(payload["name"], payload["args"])])
        return ModelResponse(parts=[TextPart(payload)])

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        kind, payload = step(messages, info)
        if kind == "tool":
            yield {0: DeltaToolCall(name=payload["name"], json_args=json.dumps(payload["args"]))}
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
    return "text", f"{share}% of scheduled passenger departures from ANC are Long-haul Flights (≥ 3,000 mi)."


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


def _all_tools_step(messages: list[ModelMessage], info: AgentInfo) -> tuple[str, str | dict]:
    n = len(_tool_returns(messages))
    if n < len(CORE_CALLS):
        name, args = CORE_CALLS[n]
        return "tool", {"name": name, "args": args}
    return "text", "Done: every core tool answered."


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
