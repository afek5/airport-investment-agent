"""Voice call routes (SPEC §10, ADR 0004), offline: OpenAI is an httpx.MockTransport, the agent a FunctionModel.

Against both stores, like the other API tests.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db
from app.agent import agent
from app.api import guards, voice
from tests.agent.scripted import _model, scripted_model
from tests.api.conftest import login, store_call

FAKE_KEY = "sk-test-not-a-real-key"
OFFER = "v=0\r\no=- 46117 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
ANSWER = "v=0\r\no=- 1 2 IN IP4 0.0.0.0\r\ns=answer\r\n"
G3 = "What is the percentage of long haul flights out of Anchorage airport?"


class FakeOpenAI:
    """Records each request to the Live API and answers like POST /v1/live/sessions (201)."""

    def __init__(self, status: int = 201, payload: dict | None = None, raise_exc: Exception | None = None):
        self.requests: list[httpx.Request] = []
        self.status, self.raise_exc = status, raise_exc
        self.payload = payload if payload is not None else {
            "session": {"id": "live_abc123", "object": "live.session"},
            "transport": {"type": "webrtc", "sdp": ANSWER},
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raise_exc:
            raise self.raise_exc
        return httpx.Response(self.status, json=self.payload)


@pytest.fixture
def openai(monkeypatch: pytest.MonkeyPatch) -> FakeOpenAI:
    fake = FakeOpenAI()
    monkeypatch.setattr(voice, "http_transport", httpx.MockTransport(fake))
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    return fake


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any request that reaches OpenAI without the `openai` fixture fails the test instead of spending."""
    def refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unmocked request to {request.url}")
    monkeypatch.setattr(voice, "http_transport", httpx.MockTransport(refuse))


def _usage_rows(client: TestClient) -> list[dict]:
    store = db._store  # noqa: SLF001
    if store.kind == "memory":
        return list(store.usage)

    async def rows():
        return [dict(r) for r in await store.pool.fetch("SELECT * FROM usage_log ORDER BY id")]
    return store_call(client, rows)


# ───────────────────────────── status and access ─────────────────────────────


def test_voice_routes_need_a_session(client: TestClient, openai: FakeOpenAI):
    for method, path, payload in [("get", "/api/voice/status", None), ("post", "/api/voice/session", {"sdp": OFFER}),
                                  ("post", "/api/voice/analyst", {"question": G3})]:
        r = getattr(client, method)(path, **({"json": payload} if payload else {}))
        assert r.status_code == 401 and r.json()["error"] == "unauthorized", path
    assert openai.requests == []


def test_status_and_health_say_voice_is_available_only_with_a_key(client: TestClient, monkeypatch):
    login(client)
    assert client.get("/api/health").json()["voice"] is False
    r = client.get("/api/voice/status").json()
    assert r["available"] is False and r["message"] == voice.MSG_VOICE_OFF
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    assert client.get("/api/health").json()["voice"] is True
    r = client.get("/api/voice/status").json()
    assert r == {"available": True, "calls_left_today": 10, "max_call_s": 300, "model": "gpt-live-1", "message": None}
    assert FAKE_KEY not in json.dumps(r)


def test_session_without_a_key_is_503_friendly(client: TestClient):
    login(client)
    r = client.post("/api/voice/session", json={"sdp": OFFER})
    assert r.status_code == 503
    assert r.json() == {"error": "voice_unavailable", "message": voice.MSG_VOICE_OFF}


# ───────────────────────────── POST /api/voice/session ─────────────────────────────


def test_session_creates_gpt_live_1_with_client_delegation_and_passes_the_sdp_through(client: TestClient,
                                                                                       openai: FakeOpenAI):
    login(client)
    r = client.post("/api/voice/session", json={"sdp": OFFER, "conversation_id": "conv-7"})
    assert r.status_code == 200, r.text
    assert r.json() == {"session_id": "live_abc123", "sdp": ANSWER, "max_call_s": 300}
    assert FAKE_KEY not in r.text

    (req,) = openai.requests
    assert req.method == "POST" and str(req.url) == "https://api.openai.com/v1/live/sessions"
    assert req.headers["authorization"] == f"Bearer {FAKE_KEY}"
    sent = json.loads(req.content)
    assert sent["transport"] == {"type": "webrtc", "sdp": OFFER}  # the offer, byte for byte
    s = sent["session"]
    assert s["model"] == "gpt-live-1" and s["delegation"] == {"type": "client"}
    assert "audio" not in s  # WebRTC negotiates the format in SDP
    ins = s["instructions"].lower()
    assert "delegate every analytic question" in ins and "never say a number" in ins
    assert "pulling the numbers" in ins and "us airports" in ins

    rows = [u for u in _usage_rows(client) if u["kind"] == "voice"]
    assert len(rows) == 1 and rows[0]["model"] == "gpt-live-1" and rows[0]["conversation_id"] == "conv-7"
    assert float(rows[0]["cost_usd"]) == 0


def test_session_rejects_a_missing_or_bogus_offer(client: TestClient, openai: FakeOpenAI):
    login(client)
    for payload in [{}, {"sdp": ""}, {"sdp": "hello"}, {"sdp": 5}]:
        assert client.post("/api/voice/session", json=payload).status_code == 400
    assert client.post("/api/voice/session", json={"sdp": "v=0" + "x" * voice.MAX_SDP_BYTES}).status_code == 400
    assert openai.requests == []


@pytest.mark.parametrize("fake", [
    FakeOpenAI(status=401, payload={"error": {"message": "bad key"}}),
    FakeOpenAI(status=500, payload={"error": {"message": "boom"}}),
    FakeOpenAI(status=201, payload={"session": {}}),
    FakeOpenAI(raise_exc=httpx.ConnectTimeout("slow")),
], ids=["401", "500", "bad-shape", "timeout"])
def test_openai_failures_are_502_friendly_and_not_counted(client: TestClient, monkeypatch, fake: FakeOpenAI):
    monkeypatch.setattr(voice, "http_transport", httpx.MockTransport(fake))
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    login(client)
    r = client.post("/api/voice/session", json={"sdp": OFFER})
    assert r.status_code == 502 and r.json() == {"error": "voice_failed", "message": voice.MSG_VOICE_FAILED}
    assert FAKE_KEY not in r.text
    assert not [u for u in _usage_rows(client) if u["kind"] == "voice"]


def test_eleventh_call_of_the_day_across_sessions_is_429(client: TestClient, openai: FakeOpenAI):
    login(client)
    for i in range(10):
        if i == 5:  # a new session does not reset the cap: it is global
            client.cookies.clear()
            login(client)
        assert client.post("/api/voice/session", json={"sdp": OFFER}).status_code == 200
    assert client.get("/api/voice/status").json()["calls_left_today"] == 0
    r = client.post("/api/voice/session", json={"sdp": OFFER})
    assert r.status_code == 429 and r.json()["error"] == "voice_cap"
    assert "10 voice calls" in r.json()["message"]
    assert len(openai.requests) == 10


def test_analyst_rows_do_not_count_as_calls(client: TestClient, openai: FakeOpenAI, monkeypatch):
    monkeypatch.setenv("VOICE_CALLS_PER_DAY", "1")
    login(client)
    with agent.override(model=scripted_model()):
        assert client.post("/api/voice/analyst", json={"question": G3}).status_code == 200
    assert client.post("/api/voice/session", json={"sdp": OFFER}).status_code == 200
    assert client.post("/api/voice/session", json={"sdp": OFFER}).status_code == 429


def test_no_call_starts_once_the_budget_is_spent(client: TestClient, openai: FakeOpenAI, monkeypatch):
    monkeypatch.setenv("TOTAL_BUDGET_USD", "0.0001")
    login(client)
    with agent.override(model=scripted_model()):
        client.post("/api/voice/analyst", json={"question": G3})
    r = client.post("/api/voice/session", json={"sdp": OFFER})
    assert r.status_code == 429 and r.json() == {"error": "total_budget", "message": guards.MSG_TOTAL_BUDGET}
    assert openai.requests == []


# ───────────────────────────── POST /api/voice/analyst ─────────────────────────────


def test_analyst_runs_the_same_agent_in_spoken_mode_and_returns_chat_parts(client: TestClient):
    seen: list[str] = []
    prompts: list[str] = []
    g3 = scripted_model()

    def spy(messages, info):
        seen.append(info.instructions or "")
        prompts.extend(p.content for m in messages for p in getattr(m, "parts", [])
                       if type(p).__name__ == "UserPromptPart")
        return g3.function(messages, info)

    from pydantic_ai.models.function import FunctionModel

    login(client)
    with agent.override(model=FunctionModel(spy)):
        r = client.post("/api/voice/analyst", json={"conversation_id": "conv-9", "question": G3})
    assert r.status_code == 200, r.text
    j = r.json()

    # the spoken-mode instruction rides on top of the full system prompt, on every model request
    assert seen and all("Spoken mode" in s and "at most 120 words" in s and "NOT as the four-section answer" in s
                        and "Answer contract" in s for s in seen)
    # ...and the turn itself carries the spoken-mode note next to the question
    assert prompts and prompts[0] == f"{G3}\n\n{voice.SPOKEN_NOTE}" and "at most 120 words" in voice.SPOKEN_NOTE

    # the spoken text is the final answer, and its numbers come from the route_mix result
    parts = j["parts"]
    rm = next(p for p in parts if p["type"] == "tool-route_mix")
    share = rm["output"]["data"]["passenger_departures"]["share_pct"]
    assert f"{share}%" in j["text"] and "Data Confidence" in j["text"]
    assert j["tools"] == ["route_mix", "suggest_followups"]

    # the parts have the useChat shape the chat stream builds, so the Evidence panel renders them
    assert rm["state"] == "output-available" and rm["input"] == {"iata": "ANC"} and rm["toolCallId"]
    assert {"data", "sources", "data_confidence"} <= set(rm["output"])
    fu = next(p for p in parts if p["type"] == "tool-suggest_followups")
    assert fu["output"]["questions"]
    assert parts[-1]["type"] == "text" and parts[-1]["text"].strip()
    assert [p["type"] for p in parts].count("step-start") == 3
    assert j["message_id"].startswith("msg-") and j["elapsed_ms"] >= 0


def test_analyst_logs_usage_as_voice_with_the_claude_cost(client: TestClient):
    login(client)
    with agent.override(model=scripted_model()):
        assert client.post("/api/voice/analyst", json={"conversation_id": "conv-3", "question": G3}).status_code == 200
    (row,) = [u for u in _usage_rows(client) if u["kind"] == "voice"]
    assert row["conversation_id"] == "conv-3" and row["model"] != voice.VOICE_MODEL
    assert row["tools"] == ["route_mix", "suggest_followups"]
    assert row["input_tokens"] > 0 and float(row["cost_usd"]) > 0


def test_analyst_uses_the_saved_conversation_as_history(client: TestClient):
    seen: list[int] = []

    def answer(messages, info):
        seen.append(len(messages))
        return "text", "OK."

    login(client)
    saved = [{"id": "u1", "role": "user", "parts": [{"type": "text", "text": "Tell me about ANC."}]},
             {"id": "a1", "role": "assistant", "parts": [{"type": "text", "text": "ANC is a cargo hub."}]}]
    assert client.put("/api/conversations/conv-h", json={"messages": saved}).status_code == 200
    with agent.override(model=_model(answer)):
        assert client.post("/api/voice/analyst", json={"conversation_id": "conv-h", "question": "And SEA?"}).status_code == 200
        assert client.post("/api/voice/analyst", json={"question": "And SEA?"}).status_code == 200
    assert seen == [3, 1]  # saved user + assistant + the new question; no conversation, no history


def test_analyst_question_over_2000_chars_is_413_and_empty_is_400(client: TestClient):
    login(client)
    with agent.override(model=scripted_model()):
        r = client.post("/api/voice/analyst", json={"question": "x" * 2001})
        assert r.status_code == 413 and r.json()["error"] == "message_too_long"
        assert client.post("/api/voice/analyst", json={"question": "  "}).status_code == 400
        assert client.post("/api/voice/analyst", content=b"not json").status_code == 400
    assert not _usage_rows(client)


def test_analyst_respects_the_hourly_rate_limit_shared_with_chat(client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "2")
    from tests.api.test_chat import body

    login(client)
    with agent.override(model=_model(lambda m, i: ("text", "OK."))):
        assert client.post("/api/chat", json=body("hi")).status_code == 200
        assert client.post("/api/voice/analyst", json={"question": "hi"}).status_code == 200
        r = client.post("/api/voice/analyst", json={"question": "hi"})
    assert r.status_code == 429 and r.json()["error"] == "rate_limited"


@pytest.mark.parametrize("env,guard,message", [
    ({"DAILY_BUDGET_USD": "0.0001"}, "budget", guards.MSG_BUDGET),
    ({"TOTAL_BUDGET_USD": "0.0001", "DAILY_BUDGET_USD": "100"}, "total_budget", guards.MSG_TOTAL_BUDGET),
], ids=["daily", "total"])
def test_analyst_stops_at_the_daily_and_total_budget(client: TestClient, monkeypatch, env, guard, message):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    calls = []

    def counting(messages, info):
        calls.append(1)
        return "text", "An answer that costs tokens."

    login(client)
    with agent.override(model=_model(counting)):
        assert client.post("/api/voice/analyst", json={"question": "first"}).status_code == 200
        client.cookies.clear()
        login(client)  # another session: the budgets are global
        r = client.post("/api/voice/analyst", json={"question": "second"})
    assert r.status_code == 200
    j = r.json()
    assert j["guard"] == guard and j["text"] == message
    assert j["parts"] == [{"type": "text", "text": message, "state": "done"}]
    assert len(calls) == 1  # no model call once the budget is spent


def test_analyst_failure_is_502_friendly_and_still_logged(client: TestClient):
    def boom(messages, info):
        raise RuntimeError("model down")

    login(client)
    with agent.override(model=_model(boom)):
        r = client.post("/api/voice/analyst", json={"question": G3})
    assert r.status_code == 502 and r.json() == {"error": "analyst_failed", "message": voice.MSG_ANALYST_FAILED}
    assert [u["kind"] for u in _usage_rows(client)] == ["voice"]


def test_spoken_text_strips_markdown_and_keeps_table_figures():
    assert voice.spoken_text("**Answer:** 2.7% of\n- flights\n# Head") == "Answer: 2.7% of flights Head"
    table = "| Variant | Share |\n|---|---:|\n| Passenger flights | 2.7% |\n| Cargo-inclusive | 29.5% |"
    assert voice.spoken_text(table) == "Variant, Share. Passenger flights, 2.7%. Cargo-inclusive, 29.5%."
