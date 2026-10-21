"""A scripted FunctionModel: calls route_mix(ANC), then suggest_followups, then answers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel


def _tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [p for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]


def _step(messages: list[ModelMessage]) -> tuple[str, str | dict]:
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


def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    kind, payload = _step(messages)
    if kind == "tool":
        return ModelResponse(parts=[ToolCallPart(payload["name"], payload["args"])])
    return ModelResponse(parts=[TextPart(payload)])


async def scripted_stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
    kind, payload = _step(messages)
    if kind == "tool":
        yield {0: DeltaToolCall(name=payload["name"], json_args=json.dumps(payload["args"]))}
    else:
        for word in payload.split(" "):
            yield word + " "


def scripted_model() -> FunctionModel:
    return FunctionModel(scripted, stream_function=scripted_stream)
