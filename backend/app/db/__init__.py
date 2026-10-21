"""Sessions, conversation history and the usage log (SPEC §7, §9).

`PgStore` runs on Postgres (`DATABASE_URL`: docker compose locally, Neon in production).
`MemoryStore` is the same interface in process memory, used when `DATABASE_URL` is unset
(`make dev` without a database) and by the offline tests. Both are async.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


@dataclass
class UsageRecord:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tools: list[str] = field(default_factory=list)


class Store(Protocol):
    kind: str

    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...
    async def create_session(self, session_id: str, ip: str | None) -> None: ...
    async def start_usage(self, session_id: str, conversation_id: str | None, kind: str, model: str) -> int: ...
    async def finish_usage(self, usage_id: int, record: UsageRecord) -> None: ...
    async def count_usage_since(self, session_id: str, kind: str, since: datetime) -> int: ...
    async def cost_since(self, since: datetime) -> float: ...
    async def list_conversations(self, session_id: str, limit: int = 50) -> list[dict]: ...
    async def get_conversation(self, session_id: str, conversation_id: str) -> dict | None: ...
    async def put_conversation(self, session_id: str, conversation_id: str, title: str,
                               messages: list[Any]) -> dict | None: ...
    async def delete_conversation(self, session_id: str, conversation_id: str) -> bool: ...


def _now() -> datetime:
    return datetime.now(UTC)


def _summary(c: dict) -> dict:
    return {k: c[k] for k in ("id", "title", "created_at", "updated_at")}


class MemoryStore:
    """In-process store with the PgStore interface (dev without a database, offline tests)."""

    kind = "memory"

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.conversations: dict[str, dict] = {}
        self.usage: list[dict] = []

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def create_session(self, session_id: str, ip: str | None) -> None:
        self.sessions[session_id] = {"id": session_id, "ip": ip, "created_at": _now()}

    async def start_usage(self, session_id: str, conversation_id: str | None, kind: str, model: str) -> int:
        self.usage.append({"id": len(self.usage) + 1, "session_id": session_id, "conversation_id": conversation_id,
                           "kind": kind, "model": model, "input_tokens": 0, "output_tokens": 0,
                           "cost_usd": 0.0, "tools": [], "created_at": _now()})
        return len(self.usage)

    async def finish_usage(self, usage_id: int, record: UsageRecord) -> None:
        row = self.usage[usage_id - 1]
        row.update(input_tokens=record.input_tokens, output_tokens=record.output_tokens,
                   cost_usd=record.cost_usd, tools=list(record.tools))

    async def count_usage_since(self, session_id: str, kind: str, since: datetime) -> int:
        return sum(1 for u in self.usage if u["session_id"] == session_id and u["kind"] == kind
                   and u["created_at"] >= since)

    async def cost_since(self, since: datetime) -> float:
        return float(sum(u["cost_usd"] for u in self.usage if u["created_at"] >= since))

    async def list_conversations(self, session_id: str, limit: int = 50) -> list[dict]:
        own = [c for c in self.conversations.values() if c["session_id"] == session_id]
        own.sort(key=lambda c: c["updated_at"], reverse=True)
        return [_summary(c) for c in own[:limit]]

    async def get_conversation(self, session_id: str, conversation_id: str) -> dict | None:
        c = self.conversations.get(conversation_id)
        if not c or c["session_id"] != session_id:
            return None
        return {**_summary(c), "messages": json.loads(json.dumps(c["messages"]))}

    async def put_conversation(self, session_id: str, conversation_id: str, title: str,
                               messages: list[Any]) -> dict | None:
        existing = self.conversations.get(conversation_id)
        if existing and existing["session_id"] != session_id:
            return None
        now = _now()
        self.conversations[conversation_id] = {
            "id": conversation_id, "session_id": session_id, "title": title,
            "created_at": existing["created_at"] if existing else now, "updated_at": now,
            "messages": json.loads(json.dumps(messages)),
        }
        return _summary(self.conversations[conversation_id])

    async def delete_conversation(self, session_id: str, conversation_id: str) -> bool:
        c = self.conversations.get(conversation_id)
        if not c or c["session_id"] != session_id:
            return False
        del self.conversations[conversation_id]
        return True


class PgStore:
    """asyncpg pool over the SPEC §7 tables. Runs schema.sql (idempotent) on init."""

    kind = "postgres"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: Any = None

    @staticmethod
    async def _init_conn(conn: Any) -> None:
        await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")

    async def init(self) -> None:
        import asyncpg

        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5, init=self._init_conn,
                                              command_timeout=10)
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def ping(self) -> bool:
        try:
            return await self.pool.fetchval("SELECT 1") == 1
        except Exception:  # noqa: BLE001 - health reports, never raises
            log.exception("db ping failed")
            return False

    async def create_session(self, session_id: str, ip: str | None) -> None:
        await self.pool.execute("INSERT INTO sessions (id, ip) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
                                session_id, ip)

    async def start_usage(self, session_id: str, conversation_id: str | None, kind: str, model: str) -> int:
        return await self.pool.fetchval(
            "INSERT INTO usage_log (session_id, conversation_id, kind, model) VALUES ($1, $2, $3, $4) RETURNING id",
            session_id, conversation_id, kind, model)

    async def finish_usage(self, usage_id: int, record: UsageRecord) -> None:
        await self.pool.execute(
            "UPDATE usage_log SET input_tokens = $2, output_tokens = $3, cost_usd = $4, tools = $5 WHERE id = $1",
            usage_id, record.input_tokens, record.output_tokens, Decimal(str(round(record.cost_usd, 6))),
            list(record.tools))

    async def count_usage_since(self, session_id: str, kind: str, since: datetime) -> int:
        return await self.pool.fetchval(
            "SELECT count(*) FROM usage_log WHERE session_id = $1 AND kind = $2 AND created_at >= $3",
            session_id, kind, since)

    async def cost_since(self, since: datetime) -> float:
        return float(await self.pool.fetchval(
            "SELECT coalesce(sum(cost_usd), 0) FROM usage_log WHERE created_at >= $1", since))

    async def list_conversations(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = await self.pool.fetch(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE session_id = $1 "
            "ORDER BY updated_at DESC LIMIT $2", session_id, limit)
        return [dict(r) for r in rows]

    async def get_conversation(self, session_id: str, conversation_id: str) -> dict | None:
        row = await self.pool.fetchrow(
            "SELECT id, title, created_at, updated_at, messages FROM conversations WHERE id = $1 AND session_id = $2",
            conversation_id, session_id)
        return dict(row) if row else None

    async def put_conversation(self, session_id: str, conversation_id: str, title: str,
                               messages: list[Any]) -> dict | None:
        row = await self.pool.fetchrow(
            "INSERT INTO conversations (id, session_id, title, messages) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, messages = EXCLUDED.messages, updated_at = now() "
            "WHERE conversations.session_id = EXCLUDED.session_id "
            "RETURNING id, title, created_at, updated_at",
            conversation_id, session_id, title, messages)
        return dict(row) if row else None

    async def delete_conversation(self, session_id: str, conversation_id: str) -> bool:
        status = await self.pool.execute("DELETE FROM conversations WHERE id = $1 AND session_id = $2",
                                         conversation_id, session_id)
        return status.endswith(" 1")


_store: Store | None = None
_store_lock = asyncio.Lock()


def make_store(dsn: str | None = None) -> Store:
    dsn = dsn if dsn is not None else os.environ.get("DATABASE_URL", "")
    if dsn:
        return PgStore(dsn)
    log.warning("DATABASE_URL is not set: sessions, history and usage live in process memory only")
    return MemoryStore()


async def get_store() -> Store:
    """The process-wide store, initialised on first use (the API lifespan also initialises it at startup)."""
    global _store
    if _store is None:
        async with _store_lock:
            if _store is None:
                store = make_store()
                await store.init()
                _store = store
    return _store


def set_store(store: Store | None) -> None:
    """Swap the process-wide store (tests)."""
    global _store
    _store = store


async def close_store() -> None:
    global _store
    if _store is not None:
        await _store.close()
        _store = None
