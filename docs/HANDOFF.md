# HANDOFF — build plan for the builder workflow

You are building the system in `docs/SPEC.md` (the what). This file is the who/when/how. The assignment: `docs/brief/TASK.md`. Vocabulary: `/GLOSSARY.md`. Decisions: `docs/adr/`. Time box: **the whole build finishes in ≤ 8 hours of wall clock**. The brief rewards clarity, reasoning and thoughtful design over completeness or polish. When time runs short, cut polish and keep correctness and honesty about what the data can show.

## 0. Start here

### Current state (2026-10-21)
- **Exists:** planning docs (this file, SPEC, GLOSSARY, ADRs, UI-STYLE, research), the brief (`docs/brief/`), the `ui-taste` skill, `scripts/setup-wizard.sh`, and 37 MB of raw samples in `data/raw/` (gitignored).
- **Git:** `git init` is done on `main` with local identity `afek5 <24208352+afek5@users.noreply.github.com>`. Files are staged and **nothing is committed**. **No GitHub repo exists yet.** P0 makes the first commit and creates the private repo.
- **No application code exists.**

### Human prerequisites (before launching the build)
The human runs `./scripts/setup-wizard.sh` stages 1 and 3 in their own terminal, so `.env` holds `ANTHROPIC_API_KEY`, `MODEL_ID`, `ACCESS_CODE`, `SESSION_SECRET`, `DAILY_BUDGET_USD` and `RATE_LIMIT_PER_HOUR`. Stage 4 (Neon) can happen any time before P3-F. Stage 5 (Render) happens after P3-F pushes `render.yaml`.

### How to run the build
In a **new** Claude Code session in `~/Documents/HA`, paste:

> Read AGENTS.md and docs/HANDOFF.md, then use a workflow to run the build: invoke the Workflow tool with `scriptPath: "docs/build-workflow.js"` and `args: {"from": "P0", "to": "P3"}`. When it finishes, report each package's status, the open issues, and any human steps needed.

`docs/build-workflow.js` runs the phases below:
- a preflight check;
- each package as **build → independent verify → up to 2 fix rounds**, with ≤ 4 concurrent agents;
- it stops at the first phase that can't reach its done-when, or when an agent reports `blocked`.

To resume or continue, run it again with a different `from` (e.g. `{"from": "P2", "to": "P3"}`). After the human finishes wizard stages 4–5, verify the live deploy with `{"from": "LIVE", "to": "LIVE"}`. Deferred work runs with `{"from": "P4", "to": "P4"}` once the human approves.

### Agent report format (every package agent returns this)
`status` (done | blocked | failed), `summary`, `done_when_evidence` (the commands run and their observed output, one line each), `tests_run`, `contract_changes`, `files_owned_touched`, `shared_files_touched`, `open_issues`, `human_action_needed`.

### Stop and report `blocked` (instead of improvising) when
- a required public data source is down or has changed shape and no documented fallback in `docs/research/data-sources.md` covers it;
- a secret or account is missing (`.env` key, gh afek5 token, Neon or Render);
- a done-when criterion conflicts with SPEC;
- live-test spend for a package would exceed ~$1.50, or the hard cap trips: every live run is metered against a **$5.00 total** in `~/.airport-agent/live_spend.json` (`backend/tests/spend_cap.py`, `make spend`). Never edit or reset that ledger;
- the deploy passes 45 minutes.

## Ground rules (every package)

- **Tracer bullet first.** One thin, real path through every layer (real data → deterministic tool → agent → chat → evidence) works before anything widens. Every later package extends a working app.
- **Contracts.** Packages talk only through the interfaces in §2. When a contract has to change, change `backend/app/contracts.py` (and the TS mirror) in one commit and say so in the package report.
- **Red–green.** Each package lands with its own tests passing (`make test`). A package is done when its completion criterion in §3 is observably true, not when its code is written.
- **Shared working tree:** P1 agents run concurrently in the same checkout. Each agent edits only its owned paths. Shared files (`backend/pyproject.toml` + `uv.lock`, `frontend/package.json` + lockfile, `Makefile`, `docker-compose.yml`, `.env.example`, `contracts.py`/`contracts.ts`) take small additive edits only (add a dependency, add a target), with a fresh read just before each edit. Commit with an explicit path list (`git add <owned paths> <shared files touched>`, never `git add -A`). On `index.lock`, wait a few seconds and retry.
- **Git:** only the GitHub account **afek5**. Run every gh/git network command with `GH_TOKEN=$(gh auth token -u afek5)`. Never switch the global gh account. Commit small, in conventional style, ending with the attribution trailer from the session's system reminder.
- **Public-repo hygiene:** the repo becomes public at submission. It contains only original code, the public data and this design. No employer names, code or branding; no secrets (`.env` is gitignored, `.env.example` lists every variable). `docs/brief/FDE-EXAM.pdf` stays gitignored.
- **Model:** `anthropic:claude-sonnet-5-5` via `MODEL_ID`. Live tests spend real money, so run `-m live` sparingly: once per golden question when that question's package completes, and the full suite in P3.

## 1. Phases

```
P0 Scaffold + Anchorage tracer bullet (1 agent, ~1.5 h)
   └─ starts the On-Time download in the background as its very first action
                          │
P1 Fan out (≤ 4 agents in parallel, each extends the working app)
   ├─ A  Ingest completion (all Snapshot tables + coverage checks)
   ├─ B  Analytics: scoring, ranking, scorecard, congestion compare, unmet demand, query_snapshot
   ├─ C  Agent + API completion: all core tools, live tools, guards, local Postgres, history
   └─ D  Frontend shell: mission-control look, rail + history, panel with plain-table evidence
                          │
P2 Integration + verification (1–2 agents): golden G1–G6, live e2e with grounding, Playwright
                          │
P3 Ship (parallel): E Docs (DESIGN.md, README, examples) · F Deploy prepared (render.yaml, prod container verified locally)
                          │
   ── human: setup-wizard stages 4–5 (Neon + Render) ──
                          │
LIVE Deploy verified live (public URL answers G3)
                          │
P4 Deferred, only after P3 is green, in this order: charts (done) · query_public_api (done) · voice call (done) · deck (done)
```

## 2. Contracts (written in P0)

- `backend/app/contracts.py`:
  - `ToolResult`, `Source`, `DataConfidence`, `Coverage` (the SPEC §5 envelope).
  - The `data` models per tool: `RankingData`, `ScorecardData`, `ComparisonData`, `RouteMixData`, `UnmetDemandData`, `LiveTrafficData`, `OdDemandData`, `LiveDelaysData`, `AdHocData`.
  - `Weights`.
- `backend/app/analytics/__init__.py`: the analytics interface (typed signatures; P0 implements only `route_mix` and `resolve_airports`).
- `backend/app/snapshot.py`: `get_conn()`, a read-only DuckDB with one view per Snapshot table (SPEC §3), and `manifest()`.
- `frontend/lib/contracts.ts`: TS mirror of the `data` models. Evidence renderers key on the tool name.

## 3. Work packages

### P0 — Scaffold + Anchorage tracer bullet (one agent, owns everything)

1. **First action:** write `ingest/download_ontime.py` (12 months, Sep 2025 → Aug 2026; ~4 min/month via the TranStats POST; see `docs/research/data-sources.md` §3 and `docs/research/scripts/transtats_dl.py`; skip months already present, since Aug 2026 is in `data/raw/`). Launch it detached so it outlives your session: `nohup uv run python ingest/download_ontime.py > data/raw/ontime/download.log 2>&1 &`. Output goes to `data/raw/ontime/`. P1-A picks it up; check the log, don't restart it.
2. Make the first commit of the already-staged planning files, then create the monorepo: `backend/` (uv), `ingest/`, `frontend/` (Next.js), `data/{raw,snapshot}`.
3. Add `Makefile` targets (`dev`, `test`, `test-live`, `snapshot`, `build`, `up`), `docker-compose.yml` (app + postgres), the multi-stage `Dockerfile`, `.env.example` and the §2 contracts.
4. Create **private** `afek5/airport-investment-agent` (`GH_TOKEN=$(gh auth token -u afek5) gh repo create afek5/airport-investment-agent --private --source . --push`).
5. **Tracer bullet, the G3 path only:**
   - ingest **T-100 for the 12 months Aug 2025–Jul 2026 with `DEST_COUNTRY` and `ORIGIN_COUNTRY` requested** (the raw July sample lacks them); then launch the prior 12 months (Aug 2024–Jul 2025, needed for P1 growth comparisons) detached with `nohup`, logging to `data/raw/t100/download.log` plus `airports` (FAA CY2025 xlsx + OurAirports) → Parquet + manifest with coverage checks;
   - `snapshot.py`;
   - `route_mix` and `resolve_airports` with unit tests;
   - a Pydantic AI agent with those two tools plus `suggest_followups`, and the system prompt skeleton per SPEC §6;
   - `/api/chat` via `VercelAIAdapter(sdk_version=7)` with no guards yet;
   - a minimal Next.js chat (`useChat` + AI Elements) with a right panel that renders the `route_mix` evidence as a table plus the Data Confidence, Assumptions and As-of chips.

**Done when:** `docker compose up` → you ask "What is the percentage of long haul flights out of Anchorage airport?" in the browser → you get a streamed answer with the passenger share (3,000 mi definition stated), the passenger-weighted and cargo-inclusive variants and the cargo-hub explanation, and the evidence table renders. A live test of G3 passes the number-grounding check. The repo exists on afek5 and is private.

### P1-A — Ingest completion (owns `ingest/`, `data/snapshot/`, `data/raw/`)

1. Fold in the background T-100 months (check `data/raw/t100/download.log`) so `t100_routes` covers 24 months. Add the remaining SPEC §3 tables: `enplanements`, `taf` (**total = the five-component sum incl. us_flag + frgn_flag**, tested against the raw FY2024 record; the CY2024 comparison is a logged diagnostic only), `ontime_airport_month` (from the background download), `metro_population`, and CBSA per airport via the Census Geocoder coordinates endpoint (keyless, cached to `data/raw/geocoder.json`).
2. Hand-code `ingest/runway_capacity.csv` for SFO, LAX, SNA and BOS from the FAA *Airport Capacity Profiles* (2014), cited per row. Leave out any airport the profiles don't cover and note it.
3. Make `make snapshot` rebuild everything and fail loudly on missing windows or columns.

**Done when:** every SPEC §3 table exists; the manifest lists the actual months per table; T-100 covers 24 months and On-Time ≥ 6 months (12 targeted); the TAF component-sum test passes (SFO FY2024 = 24,765,642); `data/snapshot/` is ≤ 25 MB; the universe has ≥ 370 primary airports including BOS, BDL, PVD, MHT, PWM, BTV.

### P1-B — Analytics (owns `backend/app/analytics/`, `backend/tests/analytics/`)

1. Implement SPEC §4: percentiles, **median imputation (disclosed) + Provisional + not-ranked**, geometric mean, weights, Data Confidence, and the screening caveat.
2. Implement the tools `rank_airports`, `airport_scorecard`, `compare_airports` (congestion lens), `unmet_demand` (observed evidence first; the Spill Scenario labelled; `cannot_determine`) and the guarded `query_snapshot`.
3. Put all thresholds, weights and the alias table in `analytics/constants.py`.

Until P1-A lands, test against a small fixture built from the real P0 tables plus hand-made rows for the missing ones.

**Done when:** the SPEC §11 layer-1 unit tests pass, including the exact median-imputation formula (Pressure 80/missing/missing → 62), Coverage and Provisional labels naming the imputed metrics, whole-Pillar exclusion, and the TAF-total test; the determinism test passes; every function returns a valid `ToolResult` envelope.

### P1-C — Agent + API completion (owns `backend/app/{agent,api,live,db}/`, `backend/tests/{agent,api}/`)

1. Register all core tools from SPEC §5 (everything except `query_public_api`).
2. Add the live clients for BTS SODA, DOT SODA and NAS Status, with timeout, retry and TTL cache.
3. Complete the system prompt per SPEC §6.
4. Add the access-code session, the rate limit, the daily budget and usage/cost logging in **local Postgres** (docker compose), plus the conversation history routes (SPEC §7, §9).
5. Write offline tests with Pydantic AI `TestModel`/`FunctionModel`.

**Done when:** offline tests cover tool wiring, the guards (wrong code → 401, the 11th failed code attempt from one IP in an hour → 429, the 31st message in an hour → 429, a message over 2,000 chars → 413, budget hit across sessions → friendly stop, an off-topic request → scoping statement) and history round-trips; `/api/chat` streams tool parts for every core tool.

### P1-D — Frontend shell (owns `frontend/`)

1. Run the **`ui-taste` skill** (new-work and operate playbooks). The visual target is `docs/UI-STYLE.md`, which stands in for a mock-up.
2. Build the access screen, the rail + recent chats (from `/api/conversations`), the welcome state with the 4 starter chips, the conversation with inline tool steps and follow-up chips, and the Mission panel (Progress / Evidence / Trace).
3. Give each tool its own **plain-table** Evidence renderer, plus the Data Confidence badge, a Coverage/provisional mark, the Assumptions and caveats list, and As-of/window chips. Unmet demand renders as three labelled blocks plus "What the data can't tell us".
4. Support light and dark themes, desktop and phone.

**Done when:** `npm run build` produces the static export; every renderer has a fixture-driven test; the ui-taste polish pass is done at 1440px and 390px widths, with the issues found and fixed listed.

### P2 — Integration + verification (owns `tests/e2e/`, cross-package fixes)

Do these in order:
1. Golden tool tests G1–G4 against an independent pandas recomputation.
2. Live e2e G1–G6 with the number-grounding check. Iterate on the prompt and tool descriptions until all pass.
3. The Playwright smoke test.
4. Save the G1–G6 transcripts to `docs/examples.md`.

**Done when:** `make test && make test-live && make e2e` are green in one run and the transcripts are committed.

### P3-E — Docs (owns `/DESIGN.md`, `/README.md`)

Per SPEC §12. DESIGN.md runs ≤ 4 pages for a Deloitte reviewer and states plainly that the score screens candidates and does not prove profitability.

**Done when:** a fresh clone and the README quickstart reach a working chat in under 5 minutes, and DESIGN.md covers scoring methodology, key tradeoffs, where/how AI is used, and limitations.

### P3-F — Deploy, outcome 1: **prepared** (owns `render.yaml`, deploy notes)

1. Write the Render blueprint (free web service, Docker, health check `/api/health`) and the Neon `DATABASE_URL` wiring. Behind Render's proxy, the production server must take the client IP from `X-Forwarded-For` (e.g. uvicorn `--proxy-headers --forwarded-allow-ips='*'`). Otherwise the per-IP limit on failed access codes locks out every user at once. Add a test for it.
2. Add the README deploy section.
3. Push. Report `human_action_needed: ["run ./scripts/setup-wizard.sh stages 4–5"]`.

**Done when:** `render.yaml` is present and valid (the service type, Docker runtime, health check path and every env var from `.env.example` are declared, with secrets marked `sync: false`); the production image builds; that container, run locally in production mode against a Postgres URL, serves the access screen and answers G3 correctly; everything is pushed.

### LIVE — Deploy, outcome 2: **verified live** (runs only after the human finishes wizard stage 5)

> **LIVE verified (2026-10-22):** https://airport-investment-agent-n37j.onrender.com serves the access screen, `/api/health` is ok with `db: ok`, a missing or wrong code gets 401, and G3 through the public URL with the access code gives 2.7% / 6.2% / 29.5%, the 3,000-mile definition, the cargo-hub explanation and the route_mix Evidence (`tests/e2e/test_smoke_playwright.py` with `E2E_BASE_URL`, 1 passed).
>
> **Decision updated (2026-10-22): deploy on Render after all,** with one account: `render.yaml` now includes a free Render Postgres (no Neon), Render generates `SESSION_SECRET`, and the hosted demo runs with `DAILY_BUDGET_USD=1`. The human pastes only `ANTHROPIC_API_KEY` and `ACCESS_CODE` (wizard stage 3). The earlier decision follows for the record.
>
> **Decision (2026-10-21): the human chose local-only.** LIVE does not run. The README states "local-only" plainly: the reviewer runs `docker compose up` with their own key. It keeps the prepared Render + Neon deploy steps as an optional section, with no live URL.

**Done when:** `RENDER_URL` in `.env` serves the access screen; `/api/health` is ok; G3 answers correctly through the public URL with the access code; the README holds the URL. If the human deploy took more than 45 min or failed, record "local-only" in the README instead. That counts as an accepted outcome, reported as status `blocked` with the reason.

### P4 — Deferred, strictly after P3 is green

In order, each one shippable on its own:
1. ~~Bespoke Evidence charts (pillar bars, route-mix donut).~~ **Done (2026-10-21):** Pillar bars on the Ranking, a scorecard Pillar chart and route-mix donuts (shadcn chart over Recharts), fixture tests in `frontend/tests/charts.test.tsx`; `scripts/evidence_screenshots.py` regenerates the screenshots (not committed).
2. ~~`query_public_api`.~~ **Done (2026-10-21):** registered as a deferred tool (`DEFERRED_TOOLS`) next to the core, under the same output validator and final-message answer rule; offline tests in `backend/tests/agent/test_public_api.py`, one live run in `backend/tests/agent/test_live_public_api.py`.
3. ~~The voice call (SPEC §10; first verify the gpt-live-1 delegation event names in the current OpenAI docs).~~ **Done (2026-10-22, merged to main):** event names checked against the OpenAI Live docs first (SPEC §10 now holds the verified API). Backend `backend/app/api/voice.py` (`/api/voice/status`, `/session`, `/analyst`), browser `frontend/lib/voice.ts` and `frontend/components/chat/voice-call.tsx` (Call button, call bar with mm:ss, captions, End). Offline tests: `backend/tests/api/test_voice.py` (mocked OpenAI, FunctionModel agent, both stores), `frontend/tests/voice.test.ts` (fake data channel, fake timers) and `voice-ui.test.tsx`. One real round trip by `scripts/voice_roundtrip.py` (spoken G3 WAV, headless Chromium): session.started → transcript → delegation → analyst with route_mix → commentary.append with the matching delegation_id → appended → "2.7%" spoken → Evidence route_mix → session.close → session.closed, 38.9 s. Two real runs showed Claude ignoring a spoken-mode rule that sat only at the end of the system prompt, so the turn now carries a short spoken-mode note as well (checked with one analyst-only call: 84 words, all three shares).
4. ~~The 5-slide deck with the `officecli` skill, using real screenshots.~~ **Done (2026-10-22), refreshed for the live demo the same day:** `docs/deck.pptx`, built by `python3 scripts/build_deck.py` with OfficeCLI 1.0.158 from the screenshots in `docs/deck/`. Slides 1 and 4 carry the live demo URL https://airport-investment-agent-n37j.onrender.com (access code on request, never on a slide). All three screenshots come from the live site at 1440×900, light theme: G3 and G1 were each asked once from their starter chip in a fresh browser session signed in through the real access screen (two live answers, about $0.06 each against the $2 cap), and each shot waited for the follow-up chips with the mouse off the rail. The G1 page also gives slide 3's rank_airports Pillar crop. Saved conversations belong to the session that asked, so the shots were taken in that same session. The G1 shot was retaken after the answer-table fix (51c7439: Streamdown capped tables at 300px and left them scrolled to the bottom), so slide 4 shows ranks 1–7 from the top.

## 4. Human-only steps

`scripts/setup-wizard.sh` walks through these:
- an Anthropic key with a spend limit;
- an OpenAI key (voice only);
- `ACCESS_CODE`;
- a Neon database;
- a Render deploy;
- making the repo public at submission.

The builders never create accounts, change billing or flip repo visibility themselves.
