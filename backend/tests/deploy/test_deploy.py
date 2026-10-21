"""Deploy, outcome 1 (HANDOFF P3-F): the Render blueprint, the production server command, Neon wiring.

Offline: no Docker, no network, no model calls.
"""

from __future__ import annotations

import asyncio
import re
import shlex
from pathlib import Path

import httpx
import pytest
import uvicorn
import yaml
from uvicorn.main import main as uvicorn_cli

from app.api import guards
from app.db import asyncpg_connect_args
from app.main import app

ROOT = Path(__file__).resolve().parents[3]
SECRETS = {"ANTHROPIC_API_KEY", "ACCESS_CODE", "SESSION_SECRET", "DATABASE_URL", "NEON_DATABASE_URL",
           "OPENAI_API_KEY"}


def _service() -> dict:
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    (svc,) = blueprint["services"]
    return svc


def _env_example_keys() -> list[str]:
    return re.findall(r"^([A-Z][A-Z0-9_]*)=", (ROOT / ".env.example").read_text(), flags=re.M)


# ───────────────────────────── render.yaml ─────────────────────────────


def test_blueprint_is_a_free_docker_web_service_with_health_check() -> None:
    svc = _service()
    assert (svc["type"], svc["runtime"], svc["plan"]) == ("web", "docker", "free")
    assert svc["healthCheckPath"] == "/api/health"
    assert (ROOT / svc["dockerfilePath"]).is_file()
    assert "dockerCommand" not in svc  # the Dockerfile CMD (with the proxy flags) is the one start command


def test_blueprint_declares_every_env_var_and_keeps_secrets_out_of_git() -> None:
    env = {e["key"]: e for e in _service()["envVars"]}
    expected = _env_example_keys()
    assert expected, ".env.example lists no variables"
    assert set(expected) <= set(env), f"missing from render.yaml: {sorted(set(expected) - set(env))}"
    for key in SECRETS:
        assert env[key].get("sync") is False and "value" not in env[key], key
    for key, spec in env.items():
        if "value" in spec:  # only non-secrets carry a value in git
            assert key not in SECRETS


# ───────────────────────────── X-Forwarded-For ─────────────────────────────


def _production_server_args() -> list[str]:
    """The uvicorn argv from the Dockerfile CMD (`sh -c "exec uvicorn …"`), as the container runs it."""
    cmd = re.search(r"^CMD\s+(\[.*\])\s*$", (ROOT / "Dockerfile").read_text(), flags=re.M)
    assert cmd, "Dockerfile has no exec-form CMD"
    argv = yaml.safe_load(cmd.group(1))
    assert argv[:2] == ["sh", "-c"]
    words = shlex.split(argv[2].replace("${PORT}", "8000"))
    words = words[1:] if words[0] == "exec" else words
    assert words[0] == "uvicorn"
    return words[1:]


def _served_app(cli_args: list[str]):
    """The ASGI app exactly as uvicorn would wrap it for these command-line options."""
    params = uvicorn_cli.make_context("uvicorn", list(cli_args)).params
    config = uvicorn.Config(app, proxy_headers=params["proxy_headers"],
                            forwarded_allow_ips=params["forwarded_allow_ips"])
    config.load()
    return config.loaded_app


async def _bad_code(served, forwarded_for: str) -> int:
    # The TCP peer is Render's proxy (a non-loopback address), never the user.
    transport = httpx.ASGITransport(app=served, client=("10.214.7.9", 41234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/session", json={"code": "wrong"}, headers={"X-Forwarded-For": forwarded_for})
        return r.status_code


@pytest.fixture
def code_gate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACCESS_CODE", "deploy-test-code")
    guards.failed_attempts.reset()
    yield
    guards.failed_attempts.reset()


def test_production_server_takes_client_ip_from_x_forwarded_for(code_gate) -> None:
    served = _served_app(_production_server_args())

    async def scenario() -> tuple[list[int], int]:
        attacker = [await _bad_code(served, "203.0.113.5") for _ in range(guards.FAILED_CODE_LIMIT + 1)]
        other_user = await _bad_code(served, "198.51.100.23")
        return attacker, other_user

    attacker, other_user = asyncio.run(scenario())
    assert attacker[:-1] == [401] * guards.FAILED_CODE_LIMIT
    assert attacker[-1] == 429  # the brute-forcing IP is locked out
    assert other_user == 401  # everyone else behind the same proxy is not


def test_without_proxy_flags_one_user_locks_out_everyone(code_gate) -> None:
    """The failure the flags prevent: uvicorn's default only trusts 127.0.0.1, so the proxy IP is used."""
    served = _served_app(["app.main:app"])

    async def scenario() -> int:
        for _ in range(guards.FAILED_CODE_LIMIT):
            await _bad_code(served, "203.0.113.5")
        return await _bad_code(served, "198.51.100.23")

    assert asyncio.run(scenario()) == 429


# ───────────────────────────── Neon DATABASE_URL ─────────────────────────────


def test_neon_pooled_url_is_made_asyncpg_safe() -> None:
    dsn, kwargs = asyncpg_connect_args(
        "postgresql://u:p@ep-calm-sun-123-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
    assert dsn == "postgresql://u:p@ep-calm-sun-123-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert kwargs == {"statement_cache_size": 0}


def test_plain_url_is_unchanged() -> None:
    url = "postgresql://airport:airport@db:5432/airport"
    assert asyncpg_connect_args(url) == (url, {})
