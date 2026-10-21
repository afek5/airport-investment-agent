"""Live e2e G3 (real Claude; spends money). Run: make test-live (pytest -m live)."""

import os

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

from app.agent import USAGE_LIMITS, agent, answer_text
from tests.grounding import ungrounded_numbers

G3 = "What is the percentage of long haul flights out of Anchorage airport?"

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
async def test_g3_live_route_mix_and_grounding(real_snapshot):
    result = await agent.run(G3, usage_limits=USAGE_LIMITS)
    msgs = result.all_messages()
    calls = [p for m in msgs if isinstance(m, ModelResponse) for p in m.parts if isinstance(p, ToolCallPart)]
    returns = [p for m in msgs if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]
    answer = answer_text(result.new_messages())
    print("\n--- G3 answer ---\n" + answer)
    print("usage:", result.usage)

    rm_calls = [c for c in calls if c.tool_name == "route_mix"]
    assert rm_calls, f"route_mix not called; calls={[c.tool_name for c in calls]}"
    assert rm_calls[0].args_as_dict()["iata"].upper() == "ANC"
    assert any(c.tool_name == "suggest_followups" for c in calls)

    rm = next(r for r in returns if r.tool_name == "route_mix")
    content = rm.content if isinstance(rm.content, dict) else rm.content.model_dump()
    d = content["data"]
    low = answer.lower()
    assert f"{d['passenger_departures']['share_pct']}%" in answer, "passenger-flight share missing"
    assert f"{d['passenger_weighted']['share_pct']}%" in answer, "passenger-weighted share missing"
    assert f"{d['cargo_inclusive_departures']['share_pct']}%" in answer, "cargo-inclusive share missing"
    assert "3,000" in answer or "3000" in answer, "3,000 mi definition not stated"
    assert "cargo" in low and "hub" in low, "cargo-hub explanation missing"
    assert "data confidence" in low

    tool_payloads = [r.content if isinstance(r.content, (dict, str)) else r.content.model_dump() for r in returns]
    missing = ungrounded_numbers(answer, tool_payloads)
    assert not missing, f"ungrounded numbers in answer: {missing}"
