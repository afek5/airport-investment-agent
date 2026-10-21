# SPEC — Airport Investment Intelligence Agent

Deloitte Digital FDE take-home ("Airport Investment Intelligence Agent", 24 h, prioritise clarity, reasoning and thoughtful design over completeness). Vocabulary is defined in `/GLOSSARY.md`; the hard decisions and their reasons are in `/docs/adr/`. This file is the **what**. `docs/HANDOFF.md` is the **who and when**.

## 1. The brief (`docs/brief/TASK.md`), its requirements → where each is met

| Brief says | Met by |
|---|---|
| Answer: "Which airports in New England are strong candidates for terminal expansion?" | `rank_airports` with a state scope, §5, golden G1 |
| "Compare LA and Santa Ana airport congestion levels" | `compare_airports(lens="congestion")` + `live_delays`, golden G2 |
| "What is the percentage of long haul flights out of Anchorage airport?" | `route_mix`, golden G3 |
| "What is the unmet flight demand in SFO airport and why?" | `unmet_demand` + `od_demand`, golden G4 |
| Use public APIs to gather airport/aviation data | 3 live keyless gov APIs as agent tools + scripted Snapshot ingest from public endpoints (ADR 0001) |
| Rank or compare airports on defined logic/KPI | Investment Opportunity Score, §4 |
| Explain its reasoning clearly | Answer contract §6 + Mission panel Evidence/Trace §8 |
| Conversational follow-ups | multi-turn chat with persisted history, weights overridable per conversation |
| Deterministic scoring (not only LLM) | `backend/app/analytics/` pure functions; the LLM never computes a score (ADR 0002) |
| Chat interface (voice bonus) | Next.js chat §8; voice call stretch §10 (ADR 0004) |
| Communicate assumptions, uncertainty, scoping | every tool returns `assumptions` + `confidence`; answer contract §6 |
| Deliverables: source code + short design doc (scoring methodology, key tradeoffs, where/how AI is used) | repo + `/DESIGN.md` (≤ 4 pages) + README; deck stretch |

## 2. Stack (fixed)

- **Backend:** Python 3.12, FastAPI, Pydantic AI (`pydantic-ai-slim[anthropic,ui]`, pin the current release, which was 2.58.0 on 2026-10-20), DuckDB (in-process, read-only views over Parquet), httpx, asyncpg or SQLAlchemy-async for Postgres, uv for env management, pytest.
- **Model:** `anthropic:claude-sonnet-5-5`, via env `MODEL_ID` (default as given).
- **Wire protocol:** Pydantic AI `VercelAIAdapter.dispatch_request(request, agent=agent, sdk_version=7)`.
- **Frontend:** Next.js (App Router, TypeScript, `output: "export"`, static), Vercel AI SDK `ai@7` + `@ai-sdk/react` `useChat`, AI Elements (shadcn-based) components, Tailwind v4, Recharts (via shadcn chart) for pillar charts. Styling per `docs/UI-STYLE.md`.
- **Serving:** one container. FastAPI serves `/api/*` and the static Next export at `/`.
- **DB:** Postgres 16. docker compose locally, Neon free tier in prod (`DATABASE_URL`).
- **Hosting:** Render free web service from the Dockerfile (`render.yaml` blueprint).
- **Repo:** `afek5/airport-investment-agent`, private until submission.

## 3. Snapshot (data contract)

Built by `ingest/` scripts from public endpoints into `data/snapshot/*.parquet` + `data/snapshot/manifest.json` (per table: source name, URL, as-of period, row count, built_at). **The aggregated snapshot is committed to git.** `data/raw/` is gitignored and holds downloads. `make snapshot` rebuilds everything. Some raw samples are already in `data/raw/` (T-100 Jul 2026, On-Time Aug 2026, FAA CY2025 xlsx, TAF 2025 zip, OurAirports, CBSA population, BEA). Source facts, endpoints and gotchas are in `docs/research/data-sources.md`, and a working TranStats downloader is in `docs/research/scripts/transtats_dl.py`. Read both before writing ingest code.

| Table | Grain | Columns (minimum) | Source | Window |
|---|---|---|---|---|
| `airports` | airport | iata, faa_locid, icao, name, city, state, faa_region, hub_size (L/M/S/N), is_primary, lat, lon, cbsa_code, cbsa_name, runway_count | FAA CY2025 commercial-service xlsx (universe: `S/L == "P"`) joined with OurAirports (+ runways.csv) and TAF Airports.xlsx; CBSA via Census Geocoder coordinates API (keyless), with a hand map fallback for the golden airports | current |
| `enplanements` | airport | iata, cy2024, cy2025, yoy_pct | FAA CY2025 xlsx | CY2024–CY2025 |
| `taf` | airport × fiscal year | iata, fiscal_year, is_forecast, enplanements_total (**aac + aat + commuter + us_flag + frgn_flag**), enplanements_international (us_flag + frgn_flag), ops_air_carrier, ops_itinerant_total | FAA TAF 2025 zip (strip space-padded locid; fiscal years Oct–Sep). **Test:** enplanements_total equals the five-component sum of the raw record (SFO FY2024 = 24,765,642; without the international columns it would be 17,490,518, which is wrong). **Diagnostic only** (log a warning, never fail): compare FY2024 with FAA CY2024 (SFO 25.08M), since fiscal and calendar years cover different periods. | FY2015–FY2045 |
| `t100_routes` | origin × dest × class × month | year, month, origin, dest, dest_country, service_class, distance_mi, departures_performed, departures_scheduled, seats, passengers, freight_lbs | BTS TranStats T-100 Segment All Carriers, scripted POST. **Request `DEST_COUNTRY` and `ORIGIN_COUNTRY` explicitly**: the existing raw sample lacks them, and the form drops unrequested fields silently. Aggregate away carrier and aircraft; drop `departures_performed == 0`. | 24 months ending Jul 2026 |
| `ontime_airport_month` | origin × month | origin, year, month, flights, dep_del15_share, avg_taxi_out_min, cancel_rate, nas_delay_min_per_flight, avg_dep_delay_min | BTS Reporting Carrier On-Time, scripted POST, pre-aggregated | 12 months ending Aug 2026 (minimum acceptable: 6) |
| `metro_population` | CBSA | cbsa_code, cbsa_name, pop_2020 … pop_2025 | Census PEP CBSA CSV (keyless) | 2020–2025 |
| `runway_capacity` | airport | iata, vfr_arrivals_hr, ifr_arrivals_hr, vfr_departures_hr, ifr_departures_hr, source_note | **Hand-coded CSV** for SFO, LAX, SNA and BOS only, from FAA *Airport Capacity Profiles* (2014), cited per row. If an airport isn't in the profiles, leave its row out and say so. | static |

Rules:
- **Coverage checks:** `build_snapshot.py` fails loudly when a table misses its window or a required column. The manifest records the actual months covered per table. Tools report the window they actually used ("12 months, Aug 2025–Jul 2026"). No answer claims an annual figure from a shorter window without saying so.
- Every tool reads the Snapshot through one `snapshot` module (DuckDB connection, `read_only`), never by opening files ad hoc.
- `as_of` per table comes from the manifest, and every tool response cites it.
- `service_class`: `F` = scheduled passenger, `G` = scheduled cargo, `L`/`P` = non-scheduled. "Passenger flights" means `F`.

## 4. Scoring methodology (deterministic; ADR 0002)

Universe = airports where `is_primary`. Every metric is converted to a **Percentile Score** across the universe airports that have that metric: `pct = rank(pct=True, method="average") * 100`.

| Pillar (default weight) | Metric | Definition | Weight in pillar |
|---|---|---|---|
| **Demand Momentum** (0.35) | `forecast_cagr` | TAF enplanements_total CAGR, FY2024 (last actual) → FY2035 | 0.60 |
| | `enpl_yoy` | FAA CY2024 → CY2025 % change | 0.40 |
| **Capacity Pressure** (0.40) | `load_factor` | Σ passengers / Σ seats, `service_class = F`, origin = airport, last 12 T-100 months | 0.40 |
| | `delay_share` | mean dep_del15_share weighted by flights, last 12 on-time months | 0.30 |
| | `taxi_out` | flight-weighted avg taxi-out minutes, last 12 on-time months | 0.30 |
| **Market Scale** (0.25) | `enplanements` | CY2025 enplanements (percentiles make a log transform unnecessary, so say so in DESIGN.md) | 0.70 |
| | `metro_pop` | 2025 CBSA population | 0.30 |

- **Coverage:** `delay_share` and `taxi_out` are null for airports with fewer than 1,000 reporting-carrier departures in the window (the On-Time sample is too thin), and `metro_pop` is null when there is no CBSA. Coverage = measured metrics out of 7.
- **Missing metrics are imputed at the median (50th percentile).** This is a stated Assumption, not a neutral operation: it pulls the Pillar toward the middle, so it can raise or lower an airport compared with its unknown true value. For example, Pressure with percentiles 80/20/20 scores 44, while 80/missing/missing scores 62. We prefer it to renormalising over the available metrics, which silently substitutes the airport's own other strengths for the gap. Here the bias always points toward the median, and it is always disclosed: any airport below 7/7 Coverage gets a **Provisional Score**, shown with its Coverage and the names of the imputed metrics.
- **Pillar score** = weighted mean of its metric percentiles, with imputed metrics included at 50.
- **Not ranked:** an airport with **no measured metric in a whole Pillar** is listed separately as "not ranked: insufficient data".
- **Investment Opportunity Score** = `exp(Σ w_p · ln(max(pillar_p, 1)))`. Range 1–100.
- **Weights** are overridable per call (`weights={"momentum":…, "pressure":…, "scale":…}`, normalised to sum 1). Defaults live in one constants module.
- **Data Confidence** (deterministic; about the evidence, not about investment success):
  - **High**: 7/7 Coverage.
  - **Medium**: 5–6 of 7, a scenario-based or estimate result, or an ad-hoc result.
  - **Low**: 4 or fewer of 7.
  - Reasons are listed (e.g. "no On-Time coverage: fewer than 1,000 reporting-carrier departures").
- **Framing:** every Ranking output carries the fixed caveat that this is a screening signal and does not establish renovation profitability (no cost, terminal-utilisation, revenue or feasibility data).
- Determinism test: the same Snapshot + the same weights → byte-identical ranking JSON.

### Unmet Demand (`unmet_demand(iata)`)

The answer is built on **observed** evidence. The scenario is a separate, labelled add-on.

1. **Constraint Evidence (observed, primary):**
   - delay_share and taxi_out vs the national median of primary airports;
   - NAS-delay minutes per flight;
   - the `runway_capacity` IFR vs VFR arrival rate drop (%) when the airport is in the table;
   - share of route-months with LF > 0.85, and seat growth vs passenger growth over the last 12 vs the prior 12 months (passengers growing faster than seats suggests supply is not keeping up);
   - `live_delays` if the airport is currently impacted.
2. **Forecast Gap (official forecast):** TAF total enplanements (incl. international) and air-carrier ops, FY2024 → FY2030, absolute and %.
3. **Spill Scenario (sensitivity, explicitly not observed):** for route-months (class F) with LF > 0.85, apply assumed spill rates of 2–5% (LF 0.85–0.90), 5–10% (0.90–0.95) and 10–15% (> 0.95). Sum over 12 months to get a `[low, high]` range plus the top 5 routes. Every parameter is returned as an Assumption, and the output is labelled "scenario under assumed spill rates; not calibrated".
4. **`cannot_determine`** (fixed list, always returned):
   - actual denied or turned-away passengers;
   - demand that recaptured to nearby airports (e.g. OAK/SJC);
   - whether the binding constraint is terminal, gates or runway/airspace;
   - airline network choices vs infrastructure limits;
   - project cost and revenue.
5. Output: the evidence list (each with value, benchmark, source, as_of), forecast gap, scenario, `cannot_determine`, a deterministic `why_drivers` list ordered by strength (built from observed evidence only), and Data Confidence Medium.

### Long-haul (`route_mix(iata, min_miles=3000, include_cargo=False)`)

Over the last 12 T-100 months, origin = airport:
- share of departures_performed with distance ≥ min_miles (class F by default);
- passenger-weighted share;
- the cargo-inclusive departures share (all classes), always returned as a labelled variant;
- pre-computed group aggregates (non-passenger G+L+P and all-cargo G+P long-haul counts and shares, and each class's share of departures and of long-haul departures), so the agent quotes them and never adds rows itself;
- the top 10 long-haul destinations by departures.

### Congestion lens (`compare_airports(lens="congestion")`)

Per airport: delay_share, avg taxi_out, cancel_rate, nas_delay_min_per_flight, monthly departures (T-100), departures per runway per day (runway_count), load_factor, national percentile of each, plus the live NAS status. A derived `congestion_index` = mean percentile of delay_share, taxi_out and nas_delay_min_per_flight, labelled as a lens and not as the Investment Opportunity Score.

## 5. Agent tools

Every tool returns the same envelope (Pydantic model `ToolResult`):

```
{ "data": {...}, "sources": [{"name","url","as_of","window"}], "assumptions": [str],
  "data_confidence": {"level": "High|Medium|Low", "reasons": [str]},
  "coverage": {"measured": int, "of": int} | null, "caveats": [str], "ad_hoc": bool }
```

| Tool | Purpose | Notes |
|---|---|---|
| `resolve_airports(query)` | names/cities/codes → airport candidates | alias table: "LA" → LAX (alternates BUR, LGB, ONT; SNA is "Santa Ana/Orange County"); returns an Assumption |
| `rank_airports(states?, faa_region?, hub_sizes?, pillar="overall", weights?, top_n=10)` | Ranking within a scope | the LLM maps region names to states; New England = CT, ME, MA, NH, RI, VT |
| `airport_scorecard(iata, weights?)` | full breakdown: raw value, percentile, pillar, national rank, rank within hub size, coverage | |
| `compare_airports(iatas[2..6], lens="congestion"\|"demand"\|"scorecard")` | side by side | |
| `route_mix(iata, min_miles=3000, include_cargo=False)` | Long-haul share | §4 |
| `unmet_demand(iata)` | observed Constraint Evidence + Forecast Gap, a separately labelled Spill Scenario, and `cannot_determine` | §4 |
| `live_traffic(iata, months=12)` | **LIVE** BTS SODA `data.bts.gov/resource/r495-tyji.json` | Live Signal; never feeds scores |
| `od_demand(iata, top_n=10)` | **LIVE** DOT Airfare SODA `data.transportation.gov/resource/tfrh-tu9e.json` | O&D pax/day, fares, carrier share |
| `live_delays(iatas?)` | **LIVE** FAA NAS Status XML | an empty result means "no active delay" |
| `query_snapshot(sql)` | escape hatch: read-only SQL over Snapshot views | SELECT/WITH only (reject anything else via a parser check plus a DuckDB read-only connection), 200-row cap, 5 s timeout; the data dictionary is in the system prompt; `ad_hoc=true`, Data Confidence ≤ Medium; SQL shown in the trace |
| `query_public_api(dataset, select?, where?, group?, order?, limit≤500)` | **built (P4, after core)**: escape hatch for live SoQL, used only when no core tool answers | whitelist: `bts_airport_month` (r495-tyji), `dot_airfare_pairs` (tfrh-tu9e), `dot_airfare_city_pairs` (yj5y-b2ir); clause bodies only (`$`, `&`, `;`, `#`, `\|>` refused), limit clamped to 1–500; live-client timeout/retry/cache; a Socrata 400 goes back to the model as a retry; `ad_hoc=true`, Data Confidence ≤ Medium; SoQL shown in the trace |
| `suggest_followups(questions[2..3])` | UI renders clickable chips | called last in every analytic answer |

Live tools: 8 s timeout, one retry, in-process TTL cache (15 min), and a graceful error envelope ("live source unavailable; answering from Snapshot as of …").

## 6. Answer contract (system prompt)

The agent is an airport-investment analyst. For every analytic answer:

1. **Answer:** a direct answer first. A Ranking or comparison is a compact markdown table.
2. **Why:** the drivers in plain words, referencing Pillars and metrics with their values.
3. **Assumptions & scope:** every Assumption and caveat the tools returned, plus any the agent made (e.g. "LA = LAX"). Ranking answers include the screening caveat (a candidate list, not proof of profitability). Unmet Demand answers include what the data cannot determine.
4. **Data Confidence:** the level and reasons, taken verbatim from the tool envelopes (the lowest level wins), plus the As-of Dates and windows. Provisional Scores are marked with their Coverage.
5. Call `suggest_followups`.

Rules for the prompt (positive phrasing):
- Every number in the answer comes from a tool result in this conversation.
- The agent answers ambiguous questions by assuming, stating the Assumption, and offering the alternative.
- Out-of-scope or unanswerable requests get a scoping statement saying what data would be needed.
- The agent uses the Glossary's terms (Investment Opportunity Score, Capacity Pressure, …).
- The system prompt includes the methodology summary, the data dictionary of Snapshot views and the tool-selection guidance. Mark it with prompt caching.

## 7. API (FastAPI)

| Route | Purpose |
|---|---|
| `POST /api/session` `{code}` | checks `ACCESS_CODE`, sets a signed httpOnly cookie with an anonymous session id |
| `POST /api/chat` | Vercel AI data stream via `VercelAIAdapter`; requires a session; enforces guards §9; logs usage |
| `GET /api/conversations`, `GET/PUT/DELETE /api/conversations/{id}` | history for the rail; the body is the useChat UI-message array (jsonb) |
| `GET /api/health` | snapshot manifest summary + DB ping |
| `POST /api/voice/session`, `POST /api/voice/analyst` | stretch §10 |

Postgres tables: `sessions`, `conversations (id, session_id, title, created_at, updated_at, messages jsonb)`, `usage_log (session_id, conversation_id, kind chat|voice, model, input_tokens, output_tokens, cost_usd, tools jsonb, created_at)`. Migrations run at startup (plain SQL file is fine).

## 8. UI

Layout and tokens: see `docs/UI-STYLE.md`. Use the `ui-taste` skill for new work and for the polish pass.

- **Access screen:** a code field, shown when there is no session.
- **Left icon rail + recent conversations** (from the API), new chat, light/dark toggle.
- **Conversation column:**
  - a welcome state with the 4 exam questions as starter chips;
  - streamed messages;
  - inline collapsed tool steps (AI Elements `Tool`) and a "Thought for Ns" row;
  - follow-up chips from `suggest_followups`;
  - a composer.
- **Right Mission panel**, three collapsible sections:
  - **Progress:** the live tool steps of the current answer.
  - **Evidence (core):** a renderer per tool `data` type, built from **plain, well-typeset tables**: the ranking (with Coverage and a provisional mark), the scorecard metric table, the comparison table, the route-mix shares, and unmet demand as three labelled blocks (Observed evidence, Forecast gap, Scenario) plus "What the data can't tell us". Plus a Data Confidence badge, the Assumptions and caveats list, and As-of/window chips.
  - **Evidence charts (P4, built after the core was green):** Pillar bars on the Ranking, a scorecard Pillar chart and route-mix donuts, drawn above the tables from the same tool `data`.
  - **Trace:** the raw tool calls (name, args, duration, ad_hoc SQL).
  - The panel opens by itself on desktop after the first tool call. On a phone it is a sheet.
- Voice "Call" button in the composer (stretch §10).

## 9. Spend and abuse guards

- Access-code gate (`ACCESS_CODE` env). All `/api/*` except `/api/session` and `/api/health` require a session.
- **Rate limit:** 30 chat messages per hour per session (counted from `usage_log`). Friendly message on overrun.
- **Daily budget:** stop at a $5/day sum of `usage_log.cost_usd` (UTC day) and show a "demo budget reached" message. Cost is computed from usage × the price table in config.
- **Access-code brute force:** `POST /api/session` allows 10 failed attempts per IP per hour (in memory is fine), then returns 429. The code is compared in constant time.
- **Per-request caps:** a user message over 2,000 characters is rejected with a friendly 413. The model call sets `max_tokens` (2,048) and a tool-call limit per answer (Pydantic AI `UsageLimits`, ≤ 12 requests).
- **Scope:** the system prompt keeps the agent to US airport and aviation investment questions. Anything else, including requests to ignore instructions or reveal the prompt, gets the scoping statement (§6) and no free-form answer. The agent has no web, shell or write tools; `query_snapshot` is read-only DuckDB.
- **Global ceiling:** the daily budget is summed across all sessions, so new sessions can't get around it. It is the hard stop on a leaked access code.
- **Voice:** max 5 min per call and 10 calls per day overall.
- Keys live only server-side (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Hard monthly limits are set in the provider consoles by the human (wizard).

## 10. Voice call (stretch, ADR 0004)

`gpt-live-1` over WebRTC in client-delegation mode:
- The browser sends its SDP to `POST /api/voice/session`, and the backend calls `POST https://api.openai.com/v1/live/sessions` with `delegation: {type: "client"}`.
- On `session.delegation.created`, the browser rebuilds the question from `session.input_transcript.delta`, then calls `POST /api/voice/analyst`. That endpoint runs the **same** Pydantic AI agent in "spoken" mode (≤ 120 words) and pushes the full tool results into the same conversation, so the Evidence panel fills.
- The browser replies to gpt-live-1 with `session.commentary.append`.
- Verify the event names against the OpenAI Live docs (`developers.openai.com/api/docs/guides/live-delegation`) before coding. They were reconstructed from docs, not run.

## 11. Acceptance — golden questions (each must pass end-to-end)

| ID | Question | Must call | Answer must contain |
|---|---|---|---|
| G1 | Which airports in New England are strong candidates for terminal expansion? | `rank_airports(states=[CT,ME,MA,NH,RI,VT])` | a ranked table of ≥ 5 New England primary airports, the top 3 explained by Pillar, Coverage and provisional marks, the screening caveat, Data Confidence, the As-of Dates |
| G2 | Compare LA and Santa Ana airport congestion levels. | `resolve_airports`, `compare_airports([LAX,SNA], "congestion")`, `live_delays` | the Assumption "LA = LAX" with alternates offered; delay share, taxi-out and cancellations for both; a verdict |
| G3 | What is the percentage of long haul flights out of Anchorage airport? | `route_mix("ANC")` | the passenger-flight share with the 3,000 mi definition stated, the passenger-weighted share, the cargo-inclusive share with the cargo-hub explanation |
| G4 | What is the unmet flight demand in SFO airport and why? | `unmet_demand("SFO")` (+ `od_demand`) | observed constraint drivers first (incl. the IFR vs VFR capacity drop), the forecast gap, the Spill Scenario explicitly labelled as an uncalibrated scenario, "what the data can't tell us", Data Confidence Medium |
| G5 | follow-up to G1: "What if growth matters twice as much?" | `rank_airports(..., weights=…)` | the changed ranking and what moved |
| G6 | "How many flights left BOS for Europe last summer?" | `query_snapshot` (uses `dest_country`) | an answer labelled ad-hoc, Data Confidence ≤ Medium, with the months used stated |

Test layers (all in CI-able pytest, except where marked live):
1. **Unit:** percentile; median imputation computed exactly per the formula (e.g. Pressure 80/missing/missing → 62); Coverage counts and Provisional labels naming the imputed metrics; exclusion ("not ranked") when a whole Pillar is missing; geometric mean, weights, TAF total including international, spill-scenario buckets, route-mix maths, SQL guard (rejects INSERT/ATTACH/COPY/PRAGMA, multiple statements).
2. **Golden tools:** for G1–G4 the tool outputs match an independent pandas recomputation from the Snapshot, plus sanity bounds (e.g. the ANC passenger long-haul share is within 1–40%).
3. **Live e2e** (`-m live`, real Claude): for G1–G6 assert that the required tools were called and that every percentage or number with ≥ 3 significant digits in the answer appears (within rounding) in some tool result in that run (the number-grounding check).
4. **Playwright smoke:** access code → ask G3 → a streamed answer + an Evidence card render → reload → the conversation persists.

## 12. Deliverables

- `/README.md`: what it is, a 60-second quickstart (`cp .env.example .env && docker compose up`), example questions, the live URL + how to get the access code, how to rebuild the Snapshot.
- `/DESIGN.md` (≤ 4 pages, the graded doc): problem framing and Investment Thesis; architecture diagram; data sources table with As-of Dates; **scoring methodology** (§4 formulas and why); Unmet Demand and Long-haul definitions; **key tradeoffs** (ADRs 0001–0004 in prose: snapshot vs live, geometric vs arithmetic, harness choice, voice delegation, hosting/guards, what we cut); **where/how AI is used** (the LLM picks tools, interprets ambiguity, writes explanations; it never computes scores or invents numbers, enforced by the tool envelopes and the grounding test); limitations and next steps (say plainly that the score screens candidates and does not prove profitability; list the data that would be needed for that: project costs, terminal and gate utilisation, commercial revenue, feasibility).
- `/docs/examples.md`: the transcripts of G1–G6 from the live run.
- Stretch: a 5-slide deck `docs/deck.pptx` built with the `officecli` skill (problem → approach → scoring → demo shots → tradeoffs/next).
