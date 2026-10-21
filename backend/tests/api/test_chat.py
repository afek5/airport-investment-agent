import json

from fastapi.testclient import TestClient

from app import db
from app.agent import ALL_TOOLS, agent
from app.api import guards
from tests.agent.scripted import all_tools_model, scripted_model
from tests.agent.stubs import stub_core_tools
from tests.api.conftest import login, store_call

G3 = "What is the percentage of long haul flights out of Anchorage airport?"


def body(text: str, chat_id: str = "chat-1") -> dict:
    return {"trigger": "submit-message", "id": chat_id,
            "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": text}]}]}


def events(raw: str) -> list[dict]:
    return [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ") and line != "data: [DONE]"]


def text_of(raw: str) -> str:
    return "".join(e["delta"] for e in events(raw) if e["type"] == "text-delta")


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["snapshot"]["tables"]["t100_routes"]["as_of"] == "Jul 2026"
    assert j["db"] == "ok" and j["db_kind"] in ("memory", "postgres")


def test_chat_streams_tool_parts_and_text(client: TestClient):
    login(client)
    with agent.override(model=scripted_model()):
        r = client.post("/api/chat", json=body(G3))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = events(r.text)
    types = [e["type"] for e in evs]
    starts = [e["toolName"] for e in evs if e["type"] == "tool-input-start"]
    assert starts == ["route_mix", "suggest_followups"]
    outputs = [e for e in evs if e["type"] == "tool-output-available"]
    rm = outputs[0]["output"]
    assert rm["data"]["iata"] == "ANC" and "data_confidence" in rm and "sources" in rm
    assert "text-delta" in types and types[-1] == "finish"


def test_chat_streams_tool_parts_for_every_core_tool(client: TestClient, monkeypatch):
    stub_core_tools(monkeypatch)
    login(client)
    with agent.override(model=all_tools_model()):
        r = client.post("/api/chat", json=body("exercise every core tool"))
    assert r.status_code == 200
    evs = events(r.text)
    starts = [e["toolName"] for e in evs if e["type"] == "tool-input-start"]
    assert starts == list(ALL_TOOLS)
    by_id = {e["toolCallId"]: e["toolName"] for e in evs if e["type"] == "tool-input-start"}
    outputs = {by_id[e["toolCallId"]]: e["output"] for e in evs if e["type"] == "tool-output-available"}
    assert set(outputs) == set(ALL_TOOLS)
    for name, out in outputs.items():
        assert ("questions" in out) if name == "suggest_followups" else {"data", "sources", "data_confidence"} <= set(out)
    assert not [e for e in evs if e["type"] in ("error", "tool-output-error")]
    assert text_of(r.text).strip() == "Done: every core tool answered."


def test_chat_logs_usage_with_tools_and_cost(client: TestClient):
    login(client)
    with agent.override(model=scripted_model()):
        r = client.post("/api/chat", json=body(G3, chat_id="conv-42"))
    assert r.status_code == 200
    store = db._store  # noqa: SLF001
    spent = store_call(client, store.cost_since, guards.utc_midnight())
    assert spent > 0
    if store.kind == "memory":
        row = store.usage[-1]
        assert row["conversation_id"] == "conv-42" and row["kind"] == "chat"
        assert row["tools"] == ["route_mix", "suggest_followups"]
        assert row["input_tokens"] > 0 and row["output_tokens"] > 0
    else:
        async def last_row():
            return dict(await store.pool.fetchrow("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1"))
        row = store_call(client, last_row)
        assert row["conversation_id"] == "conv-42" and row["tools"] == ["route_mix", "suggest_followups"]
        assert row["input_tokens"] > 0 and float(row["cost_usd"]) > 0
