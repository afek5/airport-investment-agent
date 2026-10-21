"""Conversation history routes (SPEC §7): the body is the useChat UI-message array, stored as jsonb."""

from fastapi.testclient import TestClient

from tests.api.conftest import login

MESSAGES = [
    {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "What is the percentage of long haul flights out of Anchorage airport?"}]},
    {"id": "m2", "role": "assistant", "parts": [
        {"type": "tool-route_mix", "toolCallId": "t1", "state": "output-available", "input": {"iata": "ANC"},
         "output": {"data": {"iata": "ANC", "passenger_departures": {"long_haul": 10, "total": 100, "share_pct": 10.0}},
                    "data_confidence": {"level": "High", "reasons": []}}},
        {"type": "text", "text": "**Answer** 10.0% … ✓ unicode"}]},
]


def test_round_trip_list_update_delete(client: TestClient):
    login(client)
    r = client.put("/api/conversations/conv-1", json={"messages": MESSAGES})
    assert r.status_code == 200
    saved = r.json()
    assert saved["id"] == "conv-1"
    assert saved["title"] == "What is the percentage of long haul flights out of Anchorage airport?"

    got = client.get("/api/conversations/conv-1").json()
    assert got["messages"] == MESSAGES and got["title"] == saved["title"]

    client.put("/api/conversations/conv-2", json={"title": "BOS vs PVD", "messages": MESSAGES[:1]})
    listed = client.get("/api/conversations").json()["conversations"]
    assert [c["id"] for c in listed] == ["conv-2", "conv-1"]  # most recently updated first
    assert "messages" not in listed[0] and listed[0]["title"] == "BOS vs PVD"

    # update in place keeps created_at and moves it to the top
    longer = MESSAGES + [{"id": "m3", "role": "user", "parts": [{"type": "text", "text": "and SEA?"}]}]
    r = client.put("/api/conversations/conv-1", json={"messages": longer})
    assert r.json()["created_at"] == saved["created_at"]
    assert client.get("/api/conversations/conv-1").json()["messages"] == longer
    assert [c["id"] for c in client.get("/api/conversations").json()["conversations"]] == ["conv-1", "conv-2"]

    assert client.delete("/api/conversations/conv-1").status_code == 204
    assert client.get("/api/conversations/conv-1").status_code == 404
    assert client.delete("/api/conversations/conv-1").status_code == 404
    assert [c["id"] for c in client.get("/api/conversations").json()["conversations"]] == ["conv-2"]


def test_sessions_cannot_see_or_touch_each_others_history(client: TestClient):
    login(client)
    client.put("/api/conversations/mine", json={"messages": MESSAGES})
    client.cookies.clear()
    login(client)  # a different session
    assert client.get("/api/conversations").json()["conversations"] == []
    assert client.get("/api/conversations/mine").status_code == 404
    assert client.put("/api/conversations/mine", json={"messages": []}).status_code == 404
    assert client.delete("/api/conversations/mine").status_code == 404


def test_bad_bodies_are_rejected(client: TestClient):
    login(client)
    assert client.put("/api/conversations/c", json={"messages": "nope"}).status_code == 400
    assert client.put("/api/conversations/c", content=b"{not json", headers={"content-type": "application/json"}).status_code == 400
    assert client.put("/api/conversations/" + "x" * 129, json={"messages": []}).status_code == 400
