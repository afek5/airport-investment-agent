"""HTTP routes (SPEC §7) with the spend and abuse guards (SPEC §9).

Errors are JSON `{"error": <code>, "message": <friendly text>}` with the matching status:
401 no session / wrong code, 413 message too long, 429 rate limit or too many wrong codes.
The daily budget is not an error: /api/chat streams a normal assistant message saying the demo
budget is reached (header `x-guard: budget`), so the chat shows it like any answer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    FinishChunk,
    StartChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
)
from pydantic_ai.usage import RunUsage

from app import snapshot
from app.agent import USAGE_LIMITS, agent, model_id
from app.api import guards
from app.db import UsageRecord, close_store, get_store

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await get_store()  # runs the migrations at startup (SPEC §7)
    yield
    await close_store()


router = APIRouter(prefix="/api", lifespan=lifespan)

_background: set[asyncio.Task] = set()


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _session(request: Request) -> str | None:
    return guards.verify_session(request.cookies.get(guards.SESSION_COOKIE))


def _unauthorized() -> JSONResponse:
    return _err(401, "unauthorized", guards.MSG_UNAUTHORIZED)


# ───────────────────────────── health ─────────────────────────────


@router.get("/health")
async def health() -> dict:
    m = snapshot.manifest()
    try:
        store = await get_store()
        db = "ok" if await store.ping() else "error"
        db_kind = store.kind
    except Exception:  # health reports, never raises
        log.exception("store unavailable")
        db, db_kind = "error", "unknown"
    return {
        "status": "ok",
        "snapshot": {
            "built_at": m.get("built_at"),
            "tables": {k: {"rows": v.get("rows"), "as_of": v.get("as_of"), "window": v.get("window")}
                       for k, v in m.get("tables", {}).items()},
        },
        "db": db,
        "db_kind": db_kind,
    }


# ───────────────────────────── session (access code) ─────────────────────────────


@router.get("/session")
async def session_status(request: Request) -> dict:
    return {"authenticated": _session(request) is not None}


@router.post("/session")
async def create_session(request: Request) -> Response:
    ip = _client_ip(request)
    if guards.failed_attempts.blocked(ip):
        return _err(429, "too_many_attempts", guards.MSG_TOO_MANY_CODES)
    if not guards.access_code():
        return _err(503, "not_configured", guards.MSG_NOT_CONFIGURED)
    try:
        body = await request.json()
        code = str(body.get("code", "")) if isinstance(body, dict) else ""
    except (json.JSONDecodeError, UnicodeDecodeError):
        code = ""
    if not guards.code_matches(code[:256]):
        guards.failed_attempts.record(ip)
        return _err(401, "bad_code", guards.MSG_BAD_CODE)

    session_id = guards.new_session_id()
    await (await get_store()).create_session(session_id, ip)
    resp = JSONResponse({"authenticated": True})
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(guards.SESSION_COOKIE, guards.sign_session(session_id), max_age=guards.SESSION_MAX_AGE_S,
                    httponly=True, samesite="lax", secure=secure, path="/")
    return resp


# ───────────────────────────── chat ─────────────────────────────


def last_user_text(payload: Any) -> str:
    """Text of the newest user message in a useChat request body."""
    messages = payload.get("messages") if isinstance(payload, dict) else None
    for msg in reversed(messages or []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            return "".join(p.get("text", "") for p in msg.get("parts") or []
                           if isinstance(p, dict) and p.get("type") == "text")
    return ""


def notice_stream(text: str, guard: str) -> StreamingResponse:
    """A complete assistant message in the Vercel AI UI-message stream protocol, without a model call."""
    tid = f"notice-{uuid.uuid4().hex[:8]}"
    chunks = [StartChunk(message_id=f"msg-{uuid.uuid4().hex}"), TextStartChunk(id=tid),
              TextDeltaChunk(id=tid, delta=text), TextEndChunk(id=tid), FinishChunk(finish_reason="stop"),
              DoneChunk()]
    body = "".join(f"data: {c.encode(7)}\n\n" for c in chunks)
    return StreamingResponse(iter([body]), media_type="text/event-stream",
                             headers={"x-vercel-ai-ui-message-stream": "v1", "x-guard": guard})


def _tool_names(result: Any) -> list[str]:
    return [p.tool_name for m in result.new_messages() if isinstance(m, ModelResponse)
            for p in m.parts if isinstance(p, ToolCallPart)]


@router.post("/chat")
async def chat(request: Request) -> Response:
    session_id = _session(request)
    if not session_id:
        return _unauthorized()
    raw = await request.body()  # Starlette caches it, so the adapter can read it again
    if len(raw) > guards.MAX_CHAT_BODY_BYTES:
        return _err(413, "too_large", "This conversation is too long to continue. Please start a new chat.")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err(400, "bad_request", "The request body is not valid JSON.")
    if len(last_user_text(payload)) > guards.MAX_MESSAGE_CHARS:
        return _err(413, "message_too_long", guards.MSG_TOO_LONG.format(limit=guards.MAX_MESSAGE_CHARS))

    store = await get_store()
    limit = guards.rate_limit_per_hour()
    if await store.count_usage_since(session_id, "chat", guards.hour_ago()) >= limit:
        return _err(429, "rate_limited", guards.MSG_RATE_LIMITED.format(limit=limit))
    if await store.cost_since(guards.utc_midnight()) >= guards.daily_budget_usd():
        return notice_stream(guards.MSG_BUDGET, "budget")

    conversation_id = payload.get("id") if isinstance(payload.get("id"), str) else None
    model = model_id()
    usage_id = await store.start_usage(session_id, conversation_id, "chat", model)
    run_usage, tools = RunUsage(), []

    def on_complete(result: Any) -> None:
        tools.extend(_tool_names(result))

    response = await VercelAIAdapter.dispatch_request(
        request, agent=agent, sdk_version=7, usage_limits=USAGE_LIMITS, usage=run_usage, on_complete=on_complete)

    async def finish() -> None:
        record = UsageRecord(input_tokens=run_usage.input_tokens or 0, output_tokens=run_usage.output_tokens or 0,
                             cost_usd=guards.cost_usd(run_usage, model), tools=tools)
        task = asyncio.ensure_future(store.finish_usage(usage_id, record))
        _background.add(task)
        task.add_done_callback(_background.discard)
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:  # client went away; the shielded write still completes
            pass
        except Exception:  # logging usage must never break the answer
            log.exception("usage log write failed")

    if isinstance(response, StreamingResponse):
        inner = response.body_iterator

        async def logged() -> AsyncIterator[Any]:
            try:
                async for chunk in inner:
                    yield chunk
            finally:
                await finish()

        response.body_iterator = logged()
    else:
        await finish()
    return response


# ───────────────────────────── conversation history ─────────────────────────────


def _title(messages: list[Any]) -> str:
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            text = " ".join("".join(p.get("text", "") for p in msg.get("parts") or []
                                    if isinstance(p, dict) and p.get("type") == "text").split())
            if text:
                return text if len(text) <= 80 else text[:79].rstrip() + "…"
    return "New chat"


def _valid_id(conversation_id: str) -> bool:
    return 0 < len(conversation_id) <= 128


@router.get("/conversations")
async def list_conversations(request: Request) -> Response:
    session_id = _session(request)
    if not session_id:
        return _unauthorized()
    rows = await (await get_store()).list_conversations(session_id)
    return JSONResponse({"conversations": jsonable_encoder(rows)})


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> Response:
    session_id = _session(request)
    if not session_id:
        return _unauthorized()
    row = await (await get_store()).get_conversation(session_id, conversation_id)
    if row is None:
        return _err(404, "not_found", "That conversation does not exist.")
    return JSONResponse(jsonable_encoder(row))


@router.put("/conversations/{conversation_id}")
async def put_conversation(conversation_id: str, request: Request) -> Response:
    session_id = _session(request)
    if not session_id:
        return _unauthorized()
    if not _valid_id(conversation_id):
        return _err(400, "bad_request", "Invalid conversation id.")
    raw = await request.body()
    if len(raw) > guards.MAX_CONVERSATION_BYTES:
        return _err(413, "too_large", "This conversation is too large to save.")
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err(400, "bad_request", "The request body is not valid JSON.")
    messages = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(messages, list):
        return _err(400, "bad_request", "Body must be {\"messages\": [...], \"title\"?: string}.")
    title = body.get("title") if isinstance(body.get("title"), str) and body["title"].strip() else _title(messages)
    row = await (await get_store()).put_conversation(session_id, conversation_id, title[:200], messages)
    if row is None:
        return _err(404, "not_found", "That conversation does not exist.")
    return JSONResponse(jsonable_encoder(row))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request) -> Response:
    session_id = _session(request)
    if not session_id:
        return _unauthorized()
    if not await (await get_store()).delete_conversation(session_id, conversation_id):
        return _err(404, "not_found", "That conversation does not exist.")
    return Response(status_code=204)
