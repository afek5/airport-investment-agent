"""Live e2e G1–G6 (SPEC §11 layer 3, real Claude; spends money). Run: make test-live.

For each golden question: the required tools are called, the answer carries what SPEC §11 says it
must contain, and every percentage or number with ≥ 3 significant digits in the answer appears
(within rounding) in some tool result of that run (the number-grounding check).

With WRITE_EXAMPLES=1 and every test green, the session writes the transcripts to docs/examples.md.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

from app import snapshot
from app.agent import USAGE_LIMITS, agent, answer_text, model_id
from app.api.guards import cost_usd
from tests.grounding import ungrounded_numbers

from . import recompute as rc

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"),
]

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples.md"

QUESTIONS = {
    "G1": "Which airports in New England are strong candidates for terminal expansion?",
    "G2": "Compare LA and Santa Ana airport congestion levels.",
    "G3": "What is the percentage of long haul flights out of Anchorage airport?",
    "G4": "What is the unmet flight demand in SFO airport and why?",
    "G5": "What if growth matters twice as much?",
    "G6": "How many flights left BOS for Europe last summer?",
}


@dataclass
class Run:
    gid: str
    question: str
    answer: str
    calls: list[ToolCallPart]
    returns: dict[str, list[dict]]  # tool name → payloads, this turn only
    payloads: list[Any]  # every tool payload in the conversation so far (grounding pool)
    messages: list
    cost: float
    seconds: float
    tools_in_order: list[str] = field(default_factory=list)

    def called(self, name: str) -> list[dict]:
        return [c.args_as_dict() for c in self.calls if c.tool_name == name]

    def result(self, name: str, i: int = 0) -> dict:
        return self.returns[name][i]

    @property
    def low(self) -> str:
        return norm(self.answer).lower()


RUNS: dict[str, Run] = {}


def norm(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")


def _dump(x: Any) -> Any:
    return x.model_dump(mode="json") if hasattr(x, "model_dump") else x


async def ask(gid: str, history: list | None = None) -> Run:
    t0 = time.monotonic()
    result = await agent.run(QUESTIONS[gid], message_history=history, usage_limits=USAGE_LIMITS)
    seconds = time.monotonic() - t0
    new, every = result.new_messages(), result.all_messages()
    calls = [p for m in new if isinstance(m, ModelResponse) for p in m.parts if isinstance(p, ToolCallPart)]
    returns: dict[str, list[dict]] = {}
    for m in new:
        if isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, ToolReturnPart):
                    returns.setdefault(p.tool_name, []).append(_dump(p.content))
    payloads = [_dump(p.content) for m in every if isinstance(m, ModelRequest) for p in m.parts
                if isinstance(p, ToolReturnPart)]
    # What the chat shows: the final message, after the turn's last tool call (suggest_followups).
    answer = answer_text(new)
    run = Run(gid=gid, question=QUESTIONS[gid], answer=answer, calls=calls, returns=returns,
              payloads=payloads, messages=every, cost=cost_usd(result.usage, model_id()), seconds=seconds,
              tools_in_order=[c.tool_name for c in calls])
    print(f"\n--- {gid}: {run.question}\ntools: {run.tools_in_order}\n{run.answer}\n"
          f"usage: {result.usage}  cost: ${run.cost:.4f}  {seconds:.1f}s")
    RUNS[gid] = run
    return run


def assert_common(run: Run, confidence: tuple[str, ...] = ("High", "Medium", "Low")) -> None:
    """Every analytic answer: the four contract sections, follow-ups last, and grounded numbers."""
    for label in ("answer", "why", "assumptions", "data confidence"):
        assert label in run.low, f"{run.gid}: section '{label}' missing"
    assert run.answer.count("**Data Confidence") <= 1, f"{run.gid}: the answer is not shown exactly once"
    assert run.tools_in_order and run.tools_in_order[-1] == "suggest_followups", \
        f"{run.gid}: suggest_followups must be the last tool call; got {run.tools_in_order}"
    dc = run.low[run.low.rindex("data confidence"):]
    assert any(level.lower() in dc for level in confidence), f"{run.gid}: Data Confidence not in {confidence}"
    missing = ungrounded_numbers(run.answer, run.payloads)
    assert not missing, f"{run.gid}: ungrounded numbers in answer: {missing}"


@pytest.fixture(autouse=True, scope="module")
def _real_snapshot():
    snapshot.use_snapshot_dir(rc.SNAPSHOT)
    yield


@pytest.fixture(autouse=True, scope="module")
def _write_examples(request):
    yield
    if os.environ.get("WRITE_EXAMPLES") != "1":
        return
    if request.session.testsfailed or set(RUNS) != set(QUESTIONS):
        print("\n(docs/examples.md not written: the live run was not fully green)")
        return
    EXAMPLES.write_text(render_examples())
    print(f"\nwrote {EXAMPLES}")


async def g1() -> Run:
    return RUNS.get("G1") or await ask("G1")


# ───────────────────────── G1 ─────────────────────────


async def test_g1_new_england_ranking():
    run = await g1()
    ranks = run.called("rank_airports")
    assert ranks, f"rank_airports not called: {run.tools_in_order}"
    assert set(ranks[0].get("states") or []) == set(rc.NEW_ENGLAND)
    ranked = run.result("rank_airports")["data"]["ranked"]
    assert len(ranked) >= 5
    shown = [a["iata"] for a in ranked if re.search(rf"\b{a['iata']}\b", run.answer)]
    assert len(shown) >= 5, f"answer table names fewer than 5 ranked airports: {shown}"
    assert "|" in run.answer, "the Ranking is a markdown table"
    for a in ranked[:3]:
        assert a["iata"] in run.answer
    assert "pillar" in run.low or "capacity pressure" in run.low, "top 3 explained by Pillar"
    assert "coverage" in run.low
    if any(a["provisional"] for a in ranked if a["iata"] in shown):
        assert "provisional" in run.low, "Provisional Scores must be marked"
    assert "profitab" in run.low and re.search(r"screen|candidate", run.low), "screening caveat missing"
    assert re.search(r"jul 2026|cy2025|aug 2026", run.low), "As-of Dates missing"
    assert_common(run)


# ───────────────────────── G2 ─────────────────────────


async def test_g2_la_vs_santa_ana_congestion():
    run = await ask("G2")
    assert run.called("resolve_airports"), f"resolve_airports not called: {run.tools_in_order}"
    comps = run.called("compare_airports")
    assert comps, f"compare_airports not called: {run.tools_in_order}"
    assert {c.upper() for c in comps[0]["iatas"]} == {"LAX", "SNA"}
    assert comps[0].get("lens", "congestion") == "congestion"
    assert run.called("live_delays"), f"live_delays not called: {run.tools_in_order}"
    assert re.search(r"la\W{1,3}=\W{0,3}lax|la (is|means|as) lax|\"la\" (is|means|=)", run.low) or \
        ("lax" in run.low and "assum" in run.low), "the Assumption LA = LAX is not stated"
    assert re.search(r"\b(BUR|LGB|ONT)\b", run.answer), "alternates for LA not offered"
    for word in ("delay", "taxi", "cancel"):
        assert word in run.low, f"{word} missing"
    metrics = {m["key"]: m for m in run.result("compare_airports")["data"]["metrics"]}
    for key in ("delay_share", "taxi_out", "cancel_rate"):
        for code in ("LAX", "SNA"):
            v = metrics[key]["values"][code]
            assert f"{v}" in run.answer or f"{v:g}" in run.answer, f"{key} for {code} ({v}) not quoted"
    assert_common(run)


# ───────────────────────── G3 ─────────────────────────


async def test_g3_anchorage_long_haul():
    run = await ask("G3")
    rm = run.called("route_mix")
    assert rm and rm[0]["iata"].upper() == "ANC", f"route_mix(ANC) not called: {run.tools_in_order}"
    d = run.result("route_mix")["data"]
    for key in ("passenger_departures", "passenger_weighted", "cargo_inclusive_departures"):
        assert f"{d[key]['share_pct']}%" in run.answer, f"{key} share missing"
    assert "3,000" in run.answer or "3000" in run.answer, "3,000 mi definition not stated"
    assert "cargo" in run.low and "hub" in run.low, "cargo-hub explanation missing"
    assert_common(run)


# ───────────────────────── G4 ─────────────────────────


async def test_g4_sfo_unmet_demand():
    run = await ask("G4")
    um = run.called("unmet_demand")
    assert um and um[0]["iata"].upper() == "SFO", f"unmet_demand(SFO) not called: {run.tools_in_order}"
    low = run.low
    drop = next(e for e in run.result("unmet_demand")["data"]["constraint_evidence"] if e["key"] == "ifr_arrival_drop")
    # IFR = Instrument Flight Rules; "instrument conditions" names the same drop in plain words.
    ifr = re.search(r"\bifr\b|instrument", low)
    assert ifr and f"{drop['value']}%" in run.answer, "IFR vs VFR arrival-rate drop missing"
    assert "forecast gap" in low and "2030" in low, "Forecast Gap missing"
    assert "spill scenario" in low and ("not calibrated" in low or "uncalibrated" in low), \
        "Spill Scenario not labelled as an uncalibrated scenario"
    assert "can't tell" in low or "cannot determine" in low or "can't determine" in low, \
        "'What the data can't tell us' missing"
    # Observed evidence first: the Spill Scenario is never the headline (SPEC §4, GLOSSARY "Spill Scenario").
    spill = run.result("unmet_demand")["data"]["spill_scenario"]
    answer_section = low.split("**why**")[0]
    for v in (spill["low"], spill["high"]):
        assert f"{v:,.0f}" not in answer_section, "Spill Scenario figures in the Answer section"
    assert not re.search(r"lost passengers|passengers lost|lost to full", low), "spill stated as lost passengers"
    first_spill = low.index(f"{spill['low']:,.0f}") if f"{spill['low']:,.0f}" in low else len(low)
    assert ifr.start() < first_spill and low.index("forecast gap") < first_spill, \
        "Spill Scenario presented before the observed evidence and the Forecast Gap"
    assert_common(run, confidence=("Medium",))


# ───────────────────────── G5 (follow-up to G1) ─────────────────────────


async def test_g5_growth_twice_as_much():
    base = await g1()
    run = await ask("G5", history=base.messages)
    ranks = run.called("rank_airports")
    assert ranks, f"rank_airports not called again: {run.tools_in_order}"
    res = run.result("rank_airports", -1)["data"]
    w = res["weights"]
    assert abs(w["momentum"] - 0.70 / 1.35) < 0.02, f"momentum not doubled relative to defaults: {w}"
    assert set(res.get("states") or []) == set(rc.NEW_ENGLAND), "scope changed in the follow-up"
    before = {a["iata"]: a["rank"] for a in base.result("rank_airports")["data"]["ranked"]}
    after = {a["iata"]: a["rank"] for a in res["ranked"]}
    moved = [c for c in after if before.get(c) != after[c]]
    assert moved, "the weights did not change the ranking"
    assert any(re.search(rf"\b{c}\b", run.answer) for c in moved), f"answer names none of the movers {moved}"
    assert "|" in run.answer, "the changed Ranking is a markdown table"
    assert_common(run)


# ───────────────────────── G6 ─────────────────────────


async def test_g6_bos_to_europe_last_summer():
    run = await ask("G6")
    qs = run.called("query_snapshot")
    assert qs, f"query_snapshot not called: {run.tools_in_order}"
    assert any("dest_country" in q["sql"].lower() for q in qs), "the query does not use dest_country"
    res = run.returns["query_snapshot"][-1]
    assert res["ad_hoc"] is True and res["data_confidence"]["level"] in ("Medium", "Low")
    assert "ad hoc" in run.low or "ad-hoc" in run.low, "answer not labelled ad hoc"
    assert re.search(r"jun\w*", run.low) and "2026" in run.answer, "months used not stated"
    totals = rc.bos_europe_summer_2026()
    assert any(f"{t:,}" in run.answer or f"{t}" in run.answer for t in totals.values()), \
        f"the total number of flights is not stated (recomputed: {totals})"
    assert_common(run, confidence=("Medium", "Low"))


# ───────────────────────── transcripts ─────────────────────────


def render_examples() -> str:
    total = sum(r.cost for r in RUNS.values())
    out = [
        "# Example transcripts: golden questions G1–G6",
        "",
        "Recorded from one live run of `make test-live` (real Claude, model "
        f"`{model_id()}`, Snapshot built {snapshot.manifest().get('built_at', '?')}). Every number in each "
        "answer passed the number-grounding check: it appears in a tool result of the same run. G5 is a "
        "follow-up in the G1 conversation. Regenerate with `WRITE_EXAMPLES=1 make test-live`.",
        "",
        f"Total model cost of the six answers: ${total:.2f}.",
        "",
    ]
    for gid in QUESTIONS:
        r = RUNS[gid]
        out += [f"## {gid}. {r.question}", ""]
        if gid == "G5":
            out += ["*(Follow-up in the G1 conversation.)*", ""]
        out += ["**Tool calls**", ""]
        for c in r.calls:
            args = json.dumps(c.args_as_dict(), ensure_ascii=False)
            out.append(f"- `{c.tool_name}({args})`" if len(args) < 300 else f"- `{c.tool_name}` (long arguments)")
            if c.tool_name == "query_snapshot":
                out += ["", "  ```sql", *("  " + ln for ln in c.args_as_dict()["sql"].splitlines()), "  ```", ""]
        out += ["", "**Agent response**", "", r.answer.strip(), "", f"*{r.seconds:.0f} s, ${r.cost:.3f}*", "", "---", ""]
    return "\n".join(out).rstrip("-\n") + "\n"
