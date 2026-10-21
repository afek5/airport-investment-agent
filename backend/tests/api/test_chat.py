import json

from fastapi.testclient import TestClient

from app.agent import agent
from app.main import app
from tests.agent.scripted import scripted_model

G3 = "What is the percentage of long haul flights out of Anchorage airport?"


def _body(text: str) -> dict:
    return {"trigger": "submit-message", "id": "chat-1",
            "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": text}]}]}


def _events(raw: str) -> list[dict]:
    out = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            out.append(json.loads(line[6:]))
    return out


def test_health(real_snapshot):
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["snapshot"]["tables"]["t100_routes"]["as_of"] == "Jul 2026"


def test_chat_streams_tool_parts_and_text(real_snapshot):
    with agent.override(model=scripted_model()):
        r = TestClient(app).post("/api/chat", json=_body(G3))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    types = [e["type"] for e in events]
    starts = [e["toolName"] for e in events if e["type"] == "tool-input-start"]
    assert starts == ["route_mix", "suggest_followups"]
    outputs = [e for e in events if e["type"] == "tool-output-available"]
    rm = outputs[0]["output"]
    assert rm["data"]["iata"] == "ANC" and "data_confidence" in rm and "sources" in rm
    assert "text-delta" in types and types[-1] == "finish"
