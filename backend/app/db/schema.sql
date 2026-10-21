-- Postgres schema (SPEC §7). Idempotent; runs at startup.

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    ip          TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    messages    JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS conversations_session_updated ON conversations (session_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS usage_log (
    id               BIGSERIAL PRIMARY KEY,
    session_id       TEXT NOT NULL,
    conversation_id  TEXT,
    kind             TEXT NOT NULL CHECK (kind IN ('chat', 'voice')),
    model            TEXT,
    input_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    cost_usd         NUMERIC(12, 6) NOT NULL DEFAULT 0,
    tools            JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_log_created ON usage_log (created_at);
CREATE INDEX IF NOT EXISTS usage_log_session_created ON usage_log (session_id, created_at);
