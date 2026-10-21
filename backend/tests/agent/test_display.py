"""The model reads large numbers already digit-grouped; history and contracts keep the raw values."""

from pydantic_ai.messages import ModelRequest, ToolReturnPart

from app.agent import agent
from app.agent.display import grouped
from app.agent.prompt import SYSTEM_PROMPT
from app.contracts import DataConfidence, ForecastGap, ToolResult, UnmetDemandData
from tests.agent.scripted import _model
from tests.agent.stubs import SRC, stub_core_tools


def test_grouped_formats_numbers_of_10000_or_more():
    assert grouped({"a": 30516426, "b": [24765642.0, 23.2, -12345], "c": True, "d": "SFO", "e": 1234567.5}) == \
        {"a": "30,516,426", "b": ["24,765,642", 23.2, "-12,345"], "c": True, "d": "SFO", "e": "1,234,567.5"}


def test_grouped_formats_every_count_of_1000_or_more():
    # ANC class F long-haul departures: the model printed "1005" next to "37,243" when only ≥ 10,000 was grouped.
    assert grouped({"long_haul_departures": 1005, "departures": 2289, "total": 1000, "small": 999,
                    "fare": 1234.5, "share_pct": 2.7, "neg": -1005}) == \
        {"long_haul_departures": "1,005", "departures": "2,289", "total": "1,000", "small": 999,
         "fare": "1,234.5", "share_pct": 2.7, "neg": "-1,005"}


def test_period_labels_ranks_ids_and_codes_are_never_grouped():
    out = grouped({"year": 2026, "from_fy": 2024, "to_fy": 2030, "fy": 2030, "quarter": 1, "month": 7,
                   "reporting_month": 202607, "rank": 1005, "national_rank": 1234, "airport_id": 10397,
                   "cbsa_code": 31080, "years": [2024, 2025], "monthly": [{"year": 2025, "month": 7, "departures": 4321}],
                   "months_over_threshold": 1200, "period_count": 1500})
    assert out == {"year": 2026, "from_fy": 2024, "to_fy": 2030, "fy": 2030, "quarter": 1, "month": 7,
                   "reporting_month": 202607, "rank": 1005, "national_rank": 1234, "airport_id": 10397,
                   "cbsa_code": 31080, "years": [2024, 2025], "monthly": [{"year": 2025, "month": 7, "departures": "4,321"}],
                   "months_over_threshold": "1,200", "period_count": "1,500"}


def test_ad_hoc_rows_are_grouped_by_column_name():
    table = {"columns": ["year", "quarter", "origin_airport_id", "departures", "pop_2025", "fare"],
             "rows": [[2026, 1, 10397, 1005, 4919036, 345.59], [2025, 4, 10721, 999, 1000, 375.7]],
             "row_count": 2, "truncated": False}
    assert grouped(table) == {
        "columns": ["year", "quarter", "origin_airport_id", "departures", "pop_2025", "fare"],
        "rows": [[2026, 1, 10397, "1,005", "4,919,036", 345.59], [2025, 4, 10721, 999, "1,000", 375.7]],
        "row_count": 2, "truncated": False}


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
    assert '"enplanements_to":"30,516,426"' in seen[0] and '"from_fy":2024' in seen[0] and '"to_fy":2030' in seen[0]
    stored = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)][0]
    assert stored.content.data.forecast_gap.enplanements_to == 30516426
