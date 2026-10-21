"""The model reads large numbers already digit-grouped; history and contracts keep the raw values."""

from pydantic_ai.messages import ModelRequest, ToolReturnPart

from app.agent import agent
from app.agent.display import grouped
from app.agent.prompt import SYSTEM_PROMPT
from app.contracts import DataConfidence, ForecastGap, ToolResult, UnmetDemandData
from tests.agent.scripted import _model
from tests.agent.stubs import SRC, stub_core_tools


def test_grouped_formats_only_large_numbers():
    assert grouped({"a": 30516426, "b": [24765642.0, 2030, 23.2, 9999, -12345], "c": True, "d": "SFO",
                    "e": 1234567.5}) == \
        {"a": "30,516,426", "b": ["24,765,642", 2030, 23.2, 9999, "-12,345"], "c": True, "d": "SFO",
         "e": "1,234,567.5"}


def test_prompt_carries_no_golden_figure():
    assert "30516426" not in SYSTEM_PROMPT and "30,516,426" not in SYSTEM_PROMPT


async def test_model_sees_grouped_numbers_history_keeps_raw(monkeypatch, real_snapshot):
    stub_core_tools(monkeypatch)
    gap = ForecastGap(from_fy=2024, to_fy=2030, enplanements_from=24765642, enplanements_to=30516426,
                      enplanements_abs=5750784, enplanements_pct=23.2)
    monkeypatch.setattr("app.analytics.unmet_demand", lambda iata: ToolResult[UnmetDemandData](
        data=UnmetDemandData(iata=iata, name="San Francisco", constraint_evidence=[], forecast_gap=gap,
                             spill_scenario=None, cannot_determine=[], why_drivers=[]),
        sources=SRC, data_confidence=DataConfidence(level="Medium", reasons=["test"])))
    seen: list = []

    def step(messages, info):
        returns = [p for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]
        if not returns:
            return "tool", {"name": "unmet_demand", "args": {"iata": "SFO"}}
        seen.append(returns[0].model_response_str())
        return "text", "done"

    with agent.override(model=_model(step)):
        result = await agent.run("unmet demand at SFO")
    assert '"enplanements_to":"30,516,426"' in seen[0] and '"from_fy":2024' in seen[0]
    stored = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)][0]
    assert stored.content.data.forecast_gap.enplanements_to == 30516426
