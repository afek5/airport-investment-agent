"""API fixtures: a TestClient over the real app with each store (memory, and Postgres when available).

Postgres comes from TEST_DATABASE_URL, or else a throwaway local cluster (initdb + pg_ctl) when the
binaries are installed; without either, the Postgres variants are skipped.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
from collections.abc import Iterator
from glob import glob
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.api import guards
from app.main import app

ACCESS_CODE = "test-access-code"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pg_bin(name: str) -> str | None:
    for c in [shutil.which(name), f"/opt/homebrew/bin/{name}", *sorted(glob(f"/usr/lib/postgresql/*/bin/{name}"))]:
        if c and Path(c).exists():
            return c
    return None


@pytest.fixture(scope="session")
def pg_dsn(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    if url := os.environ.get("TEST_DATABASE_URL"):
        yield url
        return
    initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("no Postgres for tests (set TEST_DATABASE_URL or install initdb/pg_ctl)")
    data = tmp_path_factory.mktemp("pg") / "data"
    port = _free_port()
    subprocess.run([initdb, "-D", str(data), "-U", "postgres", "--auth=trust", "-E", "UTF8", "--no-locale"],
                   check=True, capture_output=True)
    subprocess.run([pg_ctl, "-D", str(data), "-w", "-l", str(data.parent / "pg.log"), "-o",
                    f"-p {port} -c listen_addresses=127.0.0.1 -c unix_socket_directories=''", "start"],
                   check=True, capture_output=True)
    try:
        yield f"postgresql://postgres@127.0.0.1:{port}/postgres"
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], check=False, capture_output=True)


async def _reset_pg(dsn: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(db.SCHEMA)
        await conn.execute("TRUNCATE sessions, conversations, usage_log RESTART IDENTITY")
    finally:
        await conn.close()


@pytest.fixture(params=["memory", "postgres"])
def store_kind(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def client(store_kind: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
           real_snapshot) -> Iterator[TestClient]:
    if store_kind == "postgres":
        dsn = request.getfixturevalue("pg_dsn")
        asyncio.run(_reset_pg(dsn))
        monkeypatch.setenv("DATABASE_URL", dsn)
    else:
        monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("ACCESS_CODE", ACCESS_CODE)
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "30")
    monkeypatch.setenv("DAILY_BUDGET_USD", "5")
    guards.failed_attempts.reset()
    db.set_store(None)
    with TestClient(app) as c:  # the lifespan creates the store inside the client's event loop
        yield c
    db.set_store(None)
    guards.failed_attempts.reset()


def login(client: TestClient) -> TestClient:
    r = client.post("/api/session", json={"code": ACCESS_CODE})
    assert r.status_code == 200, r.text
    return client


def store_call(client: TestClient, fn, *args):
    """Run an async store method on the client's event loop (a Postgres pool is bound to it)."""
    return client.portal.call(fn, *args)
