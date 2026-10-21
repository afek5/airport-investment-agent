# Airport Investment Intelligence Agent

A chat agent that helps an airport-modernisation investor find US airports worth a closer look for terminal expansion. You ask a question in plain English. The agent picks deterministic analysis tools, runs them over a dated Snapshot of public FAA, BTS and Census data plus three live government APIs, and answers with a table, the drivers behind it, its Assumptions, and a Data Confidence level. Every number in an answer comes from a tool result. The language model never computes a score.

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

## Live demo: local-only

This build is local-only: there is no hosted URL. Run it with `docker compose up` as above, using your own `ANTHROPIC_API_KEY` and an `ACCESS_CODE` you choose in `.env`. The Render + Neon deploy below is prepared but optional and has not been run. A deployed copy would be gated by its access code and would stop answering for the day once it reaches its daily model budget.

## Deploy (optional: Render + Neon)

Production is one free Render web service built from the repo's `Dockerfile`, with Postgres on Neon's free tier. [`render.yaml`](render.yaml) is the Render Blueprint: Docker runtime, free plan, health check on `/api/health`, and every variable from `.env.example`. Secrets are declared with `sync: false`, so Render asks for them when the Blueprint is applied and they never enter git. `./scripts/setup-wizard.sh` stages 4 (Neon) and 5 (Render) walk through it.

1. **Neon.** Create a project (Postgres 16+, a region near Render's Ohio) and copy the pooled connection string. The app creates its tables on first start.
2. **Render.** Dashboard → Blueprints → New Blueprint Instance → this repo. When asked, paste `ANTHROPIC_API_KEY`, `ACCESS_CODE`, `SESSION_SECRET` (any long random string, so sessions survive restarts) and the Neon string as `DATABASE_URL`. Leave `NEON_DATABASE_URL`, `OPENAI_API_KEY` and `RENDER_URL` blank; the app does not read them.
3. **Check.** The service URL shows the access screen and `/api/health` returns ok. A free service sleeps when idle, so the first request after a while takes up to a minute.

Two details matter in production:

- **Client IP behind Render's proxy.** The per-IP limit on failed access codes (SPEC §9) must see the user's IP, not the proxy's, or one wrong guess streak locks out every user at once. The `Dockerfile` CMD runs uvicorn with `--proxy-headers --forwarded-allow-ips '*'` so the client IP comes from `X-Forwarded-For`. `backend/tests/deploy/test_deploy.py` checks both the fix and the failure it prevents.
- **Neon connection string.** Neon's copied string carries `channel_binding=require`, a libpq-only option that asyncpg would pass to the server, which then refuses to connect. The app drops it, and turns off asyncpg's statement cache on a `-pooler` host, since Neon's PgBouncer runs in transaction mode.

To run the production image locally the way Render runs it (the compose Postgres stands in for Neon):

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
| `make test` | Offline tests: scoring unit tests, golden-tool recomputation, API guards, frontend renderers. No API spend. |
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
backend/app/live/        clients for the three live APIs (BTS, DOT, FAA NAS Status)
backend/app/api/         FastAPI routes and the spend and abuse guards
frontend/                Next.js static chat UI with the Mission panel (Progress, Evidence, Trace)
ingest/                  scripts that build the Snapshot from public sources
data/snapshot/           the committed Snapshot
tests/e2e/               golden-question tests, live grounding tests, Playwright smoke
docs/                    spec, ADRs, research notes, example transcripts
```
