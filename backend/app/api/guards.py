"""Spend and abuse guards (SPEC §9): access-code session, brute-force limit, rate limit, budget, cost.

Settings are read from the environment at call time, so tests can monkeypatch them.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from pydantic_ai.usage import RunUsage

SESSION_COOKIE = "aia_session"
SESSION_MAX_AGE_S = 30 * 24 * 3600
MAX_MESSAGE_CHARS = 2000
MAX_CHAT_BODY_BYTES = 2_000_000  # the whole useChat history travels with each request
MAX_CONVERSATION_BYTES = 2_000_000
FAILED_CODE_LIMIT = 10  # per IP per hour; the next attempt gets 429
FAILED_CODE_WINDOW_S = 3600

# USD per million tokens. Conservative (rounded up) so the daily budget stops early rather than late.
# input = uncached input; cache_write = 5-minute cache writes; cache_read = cache hits.
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.20},
}
FALLBACK_PRICE = {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50}

# Friendly texts shown to the user. The frontend prints `message` from the JSON error body.
MSG_UNAUTHORIZED = "Enter the access code to start a session."
MSG_BAD_CODE = "That access code is not right."
MSG_TOO_MANY_CODES = "Too many wrong access codes from this network. Try again in an hour."
MSG_RATE_LIMITED = ("You have reached the demo limit of {limit} messages an hour for this session. "
                    "Please try again a little later.")
MSG_TOO_LONG = "That message is over {limit:,} characters. Please shorten it and send it again."
MSG_BUDGET = ("The demo budget for today has been reached, so the analyst is paused until 00:00 UTC. "
              "Thanks for trying it.")
MSG_NOT_CONFIGURED = "The access code is not configured on this server."


def access_code() -> str:
    return os.environ.get("ACCESS_CODE", "")


def rate_limit_per_hour() -> int:
    return int(os.environ.get("RATE_LIMIT_PER_HOUR") or 30)


def daily_budget_usd() -> float:
    return float(os.environ.get("DAILY_BUDGET_USD") or 5)


_ephemeral_secret = secrets.token_hex(32)


def _secret() -> bytes:
    # Without SESSION_SECRET the cookies are signed with a per-process key (sessions end on restart).
    return (os.environ.get("SESSION_SECRET") or _ephemeral_secret).encode()


def new_session_id() -> str:
    return secrets.token_urlsafe(18)


def sign_session(session_id: str) -> str:
    mac = hmac.new(_secret(), session_id.encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{mac}"


def verify_session(cookie: str | None) -> str | None:
    if not cookie or "." not in cookie:
        return None
    session_id, mac = cookie.rsplit(".", 1)
    expected = hmac.new(_secret(), session_id.encode(), hashlib.sha256).hexdigest()
    return session_id if hmac.compare_digest(mac, expected) else None


def code_matches(candidate: str) -> bool:
    expected = access_code()
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


class FailedAttempts:
    """Failed access-code attempts per IP over a sliding hour (in memory, SPEC §9)."""

    def __init__(self, limit: int = FAILED_CODE_LIMIT, window_s: int = FAILED_CODE_WINDOW_S, clock=time.monotonic):
        self.limit, self.window_s, self.clock = limit, window_s, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, ip: str) -> deque[float]:
        hits, cutoff = self._hits[ip], self.clock() - self.window_s
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits

    def blocked(self, ip: str) -> bool:
        with self._lock:
            return len(self._prune(ip)) >= self.limit

    def record(self, ip: str) -> None:
        with self._lock:
            self._prune(ip).append(self.clock())

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


failed_attempts = FailedAttempts()


def hour_ago() -> datetime:
    return datetime.now(UTC) - timedelta(hours=1)


def utc_midnight() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def model_name(model_id: str) -> str:
    return model_id.split(":", 1)[-1]


def cost_usd(usage: RunUsage, model_id: str) -> float:
    """Cost of a run from its token usage × the price table (Anthropic input_tokens include cache tokens)."""
    p = PRICES_PER_MTOK.get(model_name(model_id), FALLBACK_PRICE)
    cache_read, cache_write = usage.cache_read_tokens or 0, usage.cache_write_tokens or 0
    uncached = max(0, (usage.input_tokens or 0) - cache_read - cache_write)
    total = (uncached * p["input"] + cache_write * p["cache_write"] + cache_read * p["cache_read"]
             + (usage.output_tokens or 0) * p["output"])
    return round(total / 1_000_000, 6)
