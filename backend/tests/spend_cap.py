"""Hard cap on what live tests may spend on the real Anthropic key.

The human set a fixed remaining budget for this build. Every live model call from pytest goes through
`Agent.run`, which is wrapped here: before a run it refuses when the total has reached the cap, after a run
it adds the run's cost to a ledger kept outside the repo. Chat traffic through the running app is counted
too, from `usage_log` in the compose Postgres since the ledger's start.

Never edit, delete or reset the ledger to get past the cap. Report the package as blocked instead.

    uv run --project backend python -m tests.spend_cap   # print the current total
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path(os.environ.get("LIVE_SPEND_LEDGER", Path.home() / ".airport-agent" / "live_spend.json"))
DEFAULT_CAP_USD = 5.0
DB_CONTAINER = "ha-db-1"


class SpendCapReached(RuntimeError):
    pass


def _load() -> dict:
    if not LEDGER.exists():
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        data = {"cap_usd": DEFAULT_CAP_USD, "since": datetime.now(UTC).isoformat(), "pytest_usd": 0.0}
        LEDGER.write_text(json.dumps(data, indent=2))
    return json.loads(LEDGER.read_text())


def app_spend_since(since: str) -> float:
    """Sum of usage_log.cost_usd since `since` in the compose Postgres; 0 when it isn't running."""
    sql = f"SELECT coalesce(sum(cost_usd), 0) FROM usage_log WHERE created_at >= '{since}'"
    try:
        out = subprocess.run(["docker", "exec", DB_CONTAINER, "psql", "-U", "airport", "-d", "airport", "-tAc", sql],
                             check=False, capture_output=True, text=True, timeout=10)
        return float(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else 0.0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def status() -> dict:
    data = _load()
    app = app_spend_since(data["since"])
    total = data["pytest_usd"] + app
    return {**data, "app_usd": round(app, 4), "total_usd": round(total, 4),
            "remaining_usd": round(data["cap_usd"] - total, 4)}


def check() -> None:
    s = status()
    if s["total_usd"] >= s["cap_usd"]:
        raise SpendCapReached(
            f"LIVE SPEND CAP reached: ${s['total_usd']:.2f} of ${s['cap_usd']:.2f} since {s['since']}. "
            "Do not edit or reset the ledger; stop and report status 'blocked' so the human can decide.")


def record(cost: float) -> None:
    data = _load()
    data["pytest_usd"] = round(data["pytest_usd"] + cost, 6)
    LEDGER.write_text(json.dumps(data, indent=2))


def install() -> None:
    """Wrap pydantic_ai's Agent.run once so every live run is checked and recorded."""
    from pydantic_ai import Agent

    if getattr(Agent.run, "_spend_capped", False):
        return
    original = Agent.run

    @functools.wraps(original)
    async def run(self, *args, **kwargs):
        from app.agent import model_id
        from app.api.guards import cost_usd

        check()
        result = await original(self, *args, **kwargs)
        record(cost_usd(result.usage, model_id()))
        return result

    run._spend_capped = True  # noqa: SLF001 - marks our own wrapper so the cap is installed once
    Agent.run = run


def _live_selected(config) -> bool:
    expr = config.getoption("markexpr", "") or ""
    return "live" in expr and "not live" not in expr


def pytest_configure(config) -> None:
    if _live_selected(config):  # offline runs use TestModel/FunctionModel and cost nothing
        install()


def pytest_runtest_setup(item) -> None:
    import pytest

    if item.get_closest_marker("live") or item.get_closest_marker("e2e"):
        try:
            check()
        except SpendCapReached as e:
            pytest.exit(str(e), returncode=3)


def pytest_terminal_summary(terminalreporter) -> None:
    s = status()
    terminalreporter.write_line(
        f"live spend: ${s['total_usd']:.2f} of ${s['cap_usd']:.2f} cap (pytest ${s['pytest_usd']:.2f}, "
        f"app ${s['app_usd']:.2f}); ${s['remaining_usd']:.2f} left")


if __name__ == "__main__":
    print(json.dumps(status(), indent=2))
