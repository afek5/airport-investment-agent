# Airport Investment Intelligence Agent

A chat agent that helps an airport-modernisation investor find US airports worth a closer look for terminal expansion. You ask a question in plain English. The agent picks deterministic analysis tools, runs them over a dated Snapshot of public FAA, BTS and Census data plus three live government APIs, and answers with a table, the drivers behind it, its Assumptions, and a Data Confidence level. The Mission panel beside the chat shows each tool's result as tables and charts (Pillar bars, a scorecard Pillar chart, route-mix donuts) and the raw tool calls. Every number in an answer comes from a tool result. The language model never computes a score.

- **How it works and why:** [`DESIGN.md`](DESIGN.md) (scoring methodology, tradeoffs, where AI is used, limitations).
- **Example answers:** [`docs/examples.md`](docs/examples.md) has the full transcripts of the six acceptance questions from a live run.
- **Vocabulary:** [`GLOSSARY.md`](GLOSSARY.md). **Behaviour spec:** [`docs/SPEC.md`](docs/SPEC.md). **Decisions:** [`docs/adr/`](docs/adr/).

## Quickstart (Docker, about 3 minutes on first build)

You need Docker with Compose v2 and an Anthropic API key.

```bash
git clone https://github.com/afek5/airport-investment-agent.git
cd airport-investment-agent
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and pick any ACCESS_CODE
docker compose up --build
```

Open <http://localhost:8000>, enter your `ACCESS_CODE`, and click one of the four starter questions. The Snapshot is committed to the repo, so nothing is downloaded at startup. Compose also starts Postgres 16 for sessions, chat history and usage logging.

Only `ANTHROPIC_API_KEY` and `ACCESS_CODE` are required. The other variables in `.env.example` have working defaults: `MODEL_ID` (`anthropic:claude-sonnet-5-5`), `DAILY_BUDGET_USD` (5), `RATE_LIMIT_PER_HOUR` (30). Leave `SESSION_SECRET` empty and a random one is generated at each start, which signs everyone out on restart.

## Try these

| Question | What it exercises |
|---|---|
| Which airports in New England are strong candidates for terminal expansion? | Ranking by Investment Opportunity Score, Provisional Scores, screening caveat |
| Compare LA and Santa Ana airport congestion levels. | "LA = LAX" Assumption, congestion lens, live FAA delay status |
| What is the percentage of long haul flights out of Anchorage airport? | Long-haul definition (3,000 mi), passenger vs cargo-inclusive shares |
| What is the unmet flight demand in SFO airport and why? | Constraint Evidence, Forecast Gap, a labelled Spill Scenario, what the data can't tell us |
| *(follow-up)* What if growth matters twice as much? | Re-ranking with overridden Pillar Weights |
| How many flights left BOS for Europe last summer? | Ad-hoc read-only SQL over the Snapshot, labelled as such |
| What was the average fare BOS–LAX by quarter? | `query_public_api`: live SoQL on a whitelisted DOT dataset, labelled ad hoc, query shown in the Trace |

## Voice call (optional)

Set `OPENAI_API_KEY` in `.env` and a phone button appears in the composer. Press it, allow the microphone, and ask out loud, for example "What is the percentage of long haul flights out of Anchorage airport?". OpenAI's `gpt-live-1` handles the conversation and hands every analytic question to the same Claude agent the chat uses. While the agent works the call shows "Pulling the numbers…", then the voice reads a short spoken answer, and the full answer, with its tool steps and Evidence tables, lands in the chat as if you had typed it. A live caption shows what you said and what the voice said.

- Without `OPENAI_API_KEY` there is no Call button and `/api/voice/session` answers 503. Everything else works unchanged.
- The key stays on the server: the browser's WebRTC offer goes through `POST /api/voice/session`, which creates the session at OpenAI.
- Caps: each call ends itself at 5:00, and the deployment allows 10 calls per UTC day across all sessions (`VOICE_CALLS_PER_DAY`). Spoken questions count toward the 30 messages an hour, the daily budget and `TOTAL_BUDGET_USD`, like typed ones. OpenAI bills voice time separately, so set a spend limit for the key in the OpenAI console.
- Press **End** (or Enter while it has focus) to hang up. `scripts/voice_roundtrip.py` drives one real call headlessly from a spoken WAV file and saves the data-channel event log.

## Live demo

**https://airport-investment-agent-n37j.onrender.com**

The demo is gated by an access code, which the author sends with the submission. It runs on Render's free tier, so the first request after an idle spell takes up to a minute while the service wakes. To protect the model budget it answers at most 30 messages an hour per session, stops for the day after $1 of model spend, and switches off for good after $2. To run it yourself without limits, use `docker compose up` as above with your own `ANTHROPIC_API_KEY`.

## Deploy (Render, free)

[`render.yaml`](render.yaml) is a Render Blueprint: one free Docker web service built from the repo's `Dockerfile`, plus one free Render Postgres (the app creates its tables on first start). One Render account is all it takes.

1. Sign up at [render.com](https://render.com) with GitHub and give Render access to this repository.
2. **Dashboard → New → Blueprint →** pick this repo. Render reads `render.yaml` and asks for two values:
   - `ANTHROPIC_API_KEY`: your key. Set a monthly spend limit for it in the Anthropic console.
   - `ACCESS_CODE`: the password you give reviewers.
   - `OPENAI_API_KEY` (optional): leave it blank to keep the voice call off, or paste a key to turn it on. On an existing service, add it later under **Environment**.
   Render generates `SESSION_SECRET` and wires `DATABASE_URL` to the database itself.
3. **Apply.** The first build takes about 5–10 minutes. Then the service URL (`https://….onrender.com`) shows the access screen and `/api/health` returns ok. A free service sleeps when idle, so the first request after a while takes up to a minute.

**What stops strangers spending your key:** no one can chat without the access code. Each session gets 30 messages an hour, a single IP gets 10 wrong codes an hour, the whole deployment stops answering for the day once it has spent `DAILY_BUDGET_USD` ($1 in the Blueprint, about 30 answers), and stops for good once it has spent `TOTAL_BUDGET_USD` ($2), across all sessions and days. Render's free Postgres expires after 30 days.

Two details matter in production:

- **Client IP behind Render's proxy.** The per-IP limit on failed access codes (SPEC §9) must see the user's IP, not the proxy's, or one wrong guess streak locks out every user at once. The `Dockerfile` CMD runs uvicorn with `--proxy-headers --forwarded-allow-ips '*'` so the client IP comes from `X-Forwarded-For`. `backend/tests/deploy/test_deploy.py` checks both the fix and the failure it prevents.
- **Hosted Postgres URLs.** The app drops libpq-only options such as `channel_binding=require` that asyncpg would pass to the server, and turns off asyncpg's statement cache on a `-pooler` host (PgBouncer in transaction mode), so a pooled URL from another provider also works.

To run the production image locally the way Render runs it (the compose Postgres stands in for Render's):

```bash
docker compose up -d db
docker build -t airport-agent:prod .
docker run --rm -p 8010:10000 --network ha_default --env-file .env -e PORT=10000 \
  -e DATABASE_URL=postgresql://airport:airport@db:5432/airport airport-agent:prod
```

The `--network` name is the checkout's folder name followed by `_default`.

## Local development (without Docker)

Needs Python 3.12 with [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
cd backend && uv sync && cd ..
cd frontend && npm ci && cd ..
make dev        # FastAPI on :8000 (reload) + Next.js dev server on :3000
```

Open <http://localhost:3000>. Without `DATABASE_URL` the backend keeps sessions and history in memory.

| Command | What it does |
|---|---|
| `make lint` | Ruff over `backend/app`, `backend/tests`, `ingest` and `tests/e2e` (config in `backend/pyproject.toml`) and the frontend ESLint, failing on any finding or warning. |
| `make test` | `make lint`, then the offline tests: scoring unit tests, golden-tool recomputation, API guards, the grounding and count checks on recorded live answers, frontend renderers and charts. No API spend. |
| `make test-live` | Live end-to-end runs of the six golden questions against real Claude, with the number-grounding check. Spends money. |
| `make e2e` | Playwright smoke: access code, ask the Anchorage question, Evidence renders, reload keeps the conversation. Spends one answer. |
| `make build` / `make up` | Build the production image / run app + Postgres at :8000. |

## Rebuilding the Snapshot

The Snapshot is the fixed, dated data all scores run on: `data/snapshot/*.parquet` plus `manifest.json`, which records each table's source URL, As-of Date, months covered and row count. It is committed, so you only rebuild it to refresh the data.

```bash
uv run --project backend python ingest/download_t100.py                   # BTS T-100, Aug 2025–Jul 2026
uv run --project backend python ingest/download_t100.py 2024-08 2025-07   # the prior 12 months, for growth
uv run --project backend python ingest/download_ontime.py                 # BTS On-Time, ~4 min per month
make snapshot                                                             # rebuild every table from data/raw/
```

The raw downloads land in `data/raw/` (gitignored), and the downloaders skip months already present. T-100 and On-Time come from scripted BTS TranStats form posts. The FAA enplanement xlsx, the TAF 2025 zip, OurAirports `airports.csv` and `runways.csv`, and the Census CBSA population CSV are plain downloads you save into `data/raw/`. The file names `make snapshot` expects are listed at the top of `ingest/build_snapshot.py`, the URLs are in `data/snapshot/manifest.json`, and `docs/research/data-sources.md` covers every endpoint and its gotchas. `make snapshot` fails loudly if a table misses its required months or columns.

## Repository layout

```
backend/app/analytics/   deterministic scoring and analysis tools (pure functions over the Snapshot)
backend/app/agent/       the Pydantic AI agent: tool wrappers and the system prompt
backend/app/live/        clients for the three live APIs (BTS, DOT, FAA NAS Status) and query_public_api's guarded SoQL
backend/app/api/         FastAPI routes and the spend and abuse guards; voice.py is the voice call (SPEC §10)
frontend/                Next.js static chat UI with the Mission panel (Progress, Evidence tables and charts, Trace)
ingest/                  scripts that build the Snapshot from public sources
data/snapshot/           the committed Snapshot
tests/e2e/               golden-question tests, live grounding tests, Playwright smoke
scripts/                 setup wizard, query_public_api smoke call, Evidence chart screenshots (no spend), voice round trip (spends)
docs/                    spec, ADRs, research notes, example transcripts
```
