"""docs/examples.md (the last green live G1–G6 run) still passes the count check, offline.

Each answer's Snapshot tool calls, as the transcript records them, are replayed on the real Snapshot through the
agent's own tool functions (deterministic: no model, no network), and tests.grounding.misstated_counts runs on
the recorded answer against those payloads. Live tools (async: live_delays, od_demand, …) are not replayed;
no recorded count claim depends on them. G5 is a follow-up in the G1 conversation, so it also sees G1's results.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import validate_call

from app import agent as tools
from app import snapshot
from tests.grounding import misstated_counts, stated_counts

from . import recompute as rc

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "examples.md"
SECTION = re.compile(r"^## (G\d)\. .*?(?=^## G\d\. |\Z)", re.MULTILINE | re.DOTALL)
CALL = re.compile(r"^- `(\w+)\((\{.*\})\)`$", re.MULTILINE)
LONG_SQL = re.compile(r"^- `query_snapshot` \(long arguments\)\n\n  ```sql\n(.*?)\n  ```", re.MULTILINE | re.DOTALL)
ANSWER = re.compile(r"\*\*Agent response\*\*\n\n(.*?)\n\n\*\d+ s, \$[\d.]+\*", re.DOTALL)

pytestmark = pytest.mark.skipif(not (rc.SNAPSHOT / "t100_routes.parquet").exists(), reason="Snapshot not built")


@pytest.fixture(autouse=True)
def real_snapshot():
    snapshot.use_snapshot_dir(rc.SNAPSHOT)
    yield


def _sections() -> dict[str, str]:
    return {m.group(1): m.group(0) for m in SECTION.finditer(EXAMPLES.read_text())}


def _calls(section: str) -> list[tuple[str, dict[str, Any]]]:
    tool_calls = section.split("**Tool calls**", 1)[1].split("**Agent response**", 1)[0]
    found = [(m.start(), m.group(1), json.loads(m.group(2))) for m in CALL.finditer(tool_calls)]
    found += [(m.start(), "query_snapshot", {"sql": m.group(1).replace("\n  ", "\n")})
              for m in LONG_SQL.finditer(tool_calls)]
    return [(name, args) for _, name, args in sorted(found, key=lambda c: c[0])]


def _replay(section: str) -> list[Any]:
    payloads = []
    for name, args in _calls(section):
        fn = getattr(tools, name)
        if inspect.iscoroutinefunction(fn) or name == "suggest_followups":
            continue
        result = validate_call(fn)(**args)  # the arguments as the agent's tool schema validates them
        assert type(result).__name__ != "ToolError", f"{name}({args}) failed on replay: {result}"
        payloads.append(result.model_dump(mode="json"))
    return payloads


def test_examples_transcript_parses():
    sections = _sections()
    assert list(sections) == ["G1", "G2", "G3", "G4", "G5", "G6"]
    assert all(ANSWER.search(s) for s in sections.values())
    assert [n for n, _ in _calls(sections["G6"])] == ["query_snapshot", "query_snapshot", "suggest_followups"]


@pytest.mark.parametrize("gid", ["G1", "G2", "G3", "G4", "G5", "G6"])
def test_recorded_answer_passes_the_count_check(gid):
    sections = _sections()
    payloads = _replay(sections[gid]) + (_replay(sections["G1"]) if gid == "G5" else [])
    answer = ANSWER.search(sections[gid]).group(1)
    assert misstated_counts(answer, payloads) == []


def test_the_replayed_answers_do_state_counts():
    # Not vacuous: G3, G4 and G6 state window counts ("12 months", "24 months") that the tools must back.
    claims = {gid: [p for _, _, p in stated_counts(ANSWER.search(s).group(1))] for gid, s in _sections().items()}
    assert claims["G3"] and claims["G4"] and "24 months" in claims["G6"], claims
