"""Live e2e for query_public_api (real Claude and the real DOT SODA API; spends money, metered by spend_cap).

Run only this one: cd backend && set -a && . ../.env && set +a && uv run pytest -q -m live -s \
    tests/agent/test_live_public_api.py
"""

import os

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

from app.agent import USAGE_LIMITS, agent
from tests.grounding import ungrounded_numbers

Q = "What was the average fare BOS–LAX by quarter?"

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
async def test_fare_history_uses_query_public_api_and_is_grounded(real_snapshot):
    result = await agent.run(Q, usage_limits=USAGE_LIMITS)
    msgs = result.all_messages()
    calls = [p for m in msgs if isinstance(m, ModelResponse) for p in m.parts if isinstance(p, ToolCallPart)]
    returns = [p for m in msgs if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]
    answer = result.output
    print("\n--- calls ---")
    for c in calls:
        print(c.tool_name, c.args_as_dict())
    print("--- answer ---\n" + answer)
    print("usage:", result.usage)

    api_calls = [c for c in calls if c.tool_name == "query_public_api"]
    assert api_calls, f"query_public_api not chosen; calls={[c.tool_name for c in calls]}"
    assert api_calls[0].args_as_dict()["dataset"] in ("dot_airfare_pairs", "dot_airfare_city_pairs")

    api = [r for r in returns if r.tool_name == "query_public_api"]
    content = [r.content if isinstance(r.content, dict) else r.content.model_dump() for r in api]
    ok = [c for c in content if c.get("ad_hoc") and c["data"]["rows"]]
    assert ok, f"no ad-hoc rows came back: {content}"
    assert all(c["data_confidence"]["level"] in ("Medium", "Low") for c in content)
    assert "ad hoc" in answer.lower() or "ad-hoc" in answer.lower(), "answer not labelled ad hoc"

    payloads = [r.content if isinstance(r.content, (dict, str)) else r.content.model_dump() for r in returns]
    missing = ungrounded_numbers(answer, payloads)
    assert not missing, f"ungrounded numbers in answer: {missing}"
