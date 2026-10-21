"""The count check (tests.grounding.misstated_counts) on the recorded answer of the last green live
query_public_api run, offline.

The answer is verbatim from that run (tests/fixtures/live_public_api_bos_lax.json). The tool envelope comes from
the real query_public_api code with the recorded arguments, over a mock transport that returns what the live
call returned in shape: 101 quarter rows, newest first, so the tool keeps 100 (2001 Q2–2026 Q1) and marks the
result truncated. Only year and quarter are filled: the count check reads counts and wording, not fares."""

import json
from pathlib import Path

import httpx
import pytest

from app import live
from tests.grounding import misstated_counts, stated_counts, table_row_counts

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "live_public_api_bos_lax.json").read_text())


def _quarter_rows(n: int, newest: tuple[int, int] = (2026, 1)) -> list[dict[str, str]]:
    y, q = newest
    rows = []
    for _ in range(n):
        rows.append({"year": str(y), "quarter": str(q), "airport_1": "BOS", "airport_2": "LAX"})
        y, q = (y - 1, 4) if q == 1 else (y, q - 1)
    return rows


@pytest.fixture
async def envelope(monkeypatch) -> dict:
    live.clear_cache()
    rows = _quarter_rows(101)
    monkeypatch.setattr(live, "transport", httpx.MockTransport(lambda request: httpx.Response(200, json=rows)))
    r = await live.query_public_api(**FIXTURE["args"])
    live.clear_cache()
    return r.model_dump(mode="json")


async def test_recorded_envelope_matches_what_the_live_run_returned(envelope):
    got = FIXTURE["returned"]
    assert envelope["data"]["row_count"] == got["rows"] and envelope["data"]["truncated"] is got["truncated"]
    assert envelope["data"]["periods"] == got["periods"] and envelope["data"]["period_count"] == 100


async def test_recorded_live_answer_passes_the_count_check(envelope):
    answer = FIXTURE["answer"]
    # The check is not vacuous here: the answer states three counts and shows a 13-row table.
    assert [p for _, _, p in stated_counts(answer)] == ["13 quarters", "100 quarters", "100 quarters"]
    assert table_row_counts(answer) == {13}
    assert misstated_counts(answer, [envelope]) == []


async def test_recorded_answer_with_a_wrong_subset_count_fails(envelope):
    # "the last 12 quarters" above the same 13-row table: the rule the old check let through (12 < 100).
    wrong = FIXTURE["answer"].replace("shows the last 13 quarters", "shows the last 12 quarters")
    assert wrong != FIXTURE["answer"]
    assert misstated_counts(wrong, [envelope]) == ["12 quarters"]
