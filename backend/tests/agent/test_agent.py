from pydantic_ai.models.test import TestModel

from app.agent import agent
from tests.agent.scripted import scripted_model


def test_tools_registered():
    names = set(agent._function_toolset.tools)  # noqa: SLF001 - wiring check
    assert {"route_mix", "resolve_airports", "suggest_followups"} <= names


async def test_every_tool_runs_with_test_model(real_snapshot):
    """TestModel calls every registered tool once with generated arguments."""
    with agent.override(model=TestModel(call_tools=["resolve_airports", "suggest_followups"])):
        result = await agent.run("hello")
    assert result.output


async def test_scripted_g3_path_grounds_answer(real_snapshot):
    with agent.override(model=scripted_model()):
        result = await agent.run("What is the percentage of long haul flights out of Anchorage airport?")
    from app.analytics import route_mix
    share = route_mix("ANC").data.passenger_departures.share_pct
    assert f"{share}%" in result.output
