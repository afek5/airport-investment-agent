# Design: Airport Investment Intelligence Agent

## 1. Problem and Investment Thesis

An investor in US airport modernisation wants an agent that helps analysts find airports where a terminal renovation is most likely to pay off through added flight and passenger capacity. No public dataset measures renovation profitability, so the agent works from an explicit **Investment Thesis**: a renovation is most promising where demand is growing, the existing infrastructure is already strained by that demand, and the market is large enough for new capacity to be monetised. Those three clauses become the three **Pillars** of a deterministic **Investment Opportunity Score**: Demand Momentum, Capacity Pressure and Market Scale.

The score is a **screening signal**. It tells an analyst which airports deserve a closer look, and it does not show that a renovation would be profitable. Every Ranking the agent produces says so.

## 2. Architecture

```
 Browser: Next.js static chat (Vercel AI SDK useChat)        Mission panel: Progress · Evidence · Trace
        │  POST /api/chat   (UI-message stream: text + tool calls + tool results)
        ▼
 FastAPI ── guards: access code · 30 msgs/h · $5/day budget · 2,000-char cap · 12 model requests/answer
        │
        ▼
 Pydantic AI agent (Claude Sonnet 5.5)  ── chooses tools, writes the explanation, never computes
        │
        ├── deterministic tools (backend/app/analytics) ──► DuckDB, read-only ──► Snapshot (Parquet + manifest)
        │     resolve_airports · rank_airports · airport_scorecard · compare_airports
        │     route_mix · unmet_demand · query_snapshot (read-only SQL)
        ├── Live Signals (backend/app/live) ──► BTS SODA · DOT Airfare SODA · FAA NAS Status
        └── suggest_followups
 Postgres: sessions, conversation history, usage and cost log

 Offline: ingest/ scripts ──► public FAA / BTS / Census downloads ──► data/snapshot/ (committed)
```

One container serves the API and the static frontend. Every tool returns the same envelope: `data`, `sources` (with As-of Date and window), `assumptions`, `data_confidence`, `coverage`, `caveats` and an `ad_hoc` flag. The Evidence panel renders each tool's `data` as a plain table, so an analyst can check every figure in the answer against the tool output behind it.

## 3. Data

All scoring runs on the **Snapshot**: Parquet tables built by script from public endpoints and committed to the repo, with a manifest of each table's source, months covered and row count. Every tool cites the As-of Date it used.

| Table | Source | As-of / window | Feeds |
|---|---|---|---|
| `airports` (402 Primary Airports) | FAA CY2025 commercial-service list, OurAirports (runways), Census Geocoder (metro area) | CY2025 | universe, Hub Size, runways, metro area |
| `enplanements` | FAA CY2025 commercial-service enplanements | CY2024–CY2025 | growth, market size |
| `taf` | FAA Terminal Area Forecast 2025 | FY2015–FY2045 (actuals to FY2024) | forecast growth, Forecast Gap |
| `t100_routes` | BTS T-100 Segment, all carriers | 24 months, Aug 2024–Jul 2026 | Load Factor, route mix, Spill Scenario |
| `ontime_airport_month` | BTS Reporting Carrier On-Time | 12 months, Sep 2025–Aug 2026 | delays, taxi-out, cancellations |
| `metro_population` | Census Population Estimates, Vintage 2025 | Jul 1, 2025 | metro population |
| `runway_capacity` | FAA Airport Capacity Profiles, hand-coded | 2014 (LAX, SNA), 2019 (SFO, BOS) | bad-weather capacity drop |
| Live: `live_traffic` | BTS SODA `r495-tyji` | latest published month | Live Signal |
| Live: `od_demand` | DOT Consumer Airfare Report SODA `tfrh-tu9e` | latest quarter (2026 Q1) | Live Signal |
| Live: `live_delays` | FAA NAS Status XML | at question time | Live Signal |

The TAF total includes international enplanements; without them SFO's FY2024 total would read 17.5M instead of 24.8M, and a test pins the value.

## 4. Scoring methodology

**Percentiles.** Each of seven metrics becomes a **Percentile Score** across the 402 Primary Airports that have it: `pct = rank(pct=True, method="average") × 100`. Percentiles let a 2M-passenger airport be compared with a 40M one, and they keep outliers such as Anchorage's cargo traffic or Atlanta's volume from stretching the scale. Because only rank order matters, enplanements need no log transform.

| Pillar (default weight) | Metric (weight in Pillar) |
|---|---|
| **Demand Momentum** (0.35) | TAF enplanement CAGR FY2024 → FY2035 (0.60); enplanement growth CY2024 → CY2025 (0.40) |
| **Capacity Pressure** (0.40) | Load Factor, scheduled passenger flights, last 12 T-100 months (0.40); share of departures delayed ≥ 15 min (0.30); average taxi-out (0.30), both over the last 12 On-Time months |
| **Market Scale** (0.25) | CY2025 enplanements (0.70); 2025 metro (CBSA) population (0.30) |

Capacity Pressure carries the most weight because an expansion pays when demand already presses on the infrastructure; Market Scale the least, because it bounds the value without creating the need. The weights are a judgement. An analyst can override them in the conversation ("what if growth matters twice as much?"), and the agent re-runs the same scoring.

**Pillar score** = weighted mean of its metric percentiles.

**Investment Opportunity Score** = `exp(Σ w_p · ln(max(pillar_p, 1)))`, a weighted geometric mean on a 1–100 scale. The thesis is a conjunction, so a weak Pillar should hurt more than an arithmetic mean lets it. Boston (Pillars 50.2 / 86.1 / 95.3) scores 73.1, against 75.8 under an arithmetic mean. Martha's Vineyard (82.1 / 57.7 / 28.4) scores 54.7, against 58.9: its weak Market Scale costs it 4.2 points, where Boston's weaker Pillar costs it 2.7.

**Missing data.** Delay share and taxi-out are null below 1,000 reporting-carrier departures in the window, and metro population is null outside a metro or micro area. A missing metric is **imputed at the median (50)**. This choice has a direction: it pulls the Pillar toward the middle. Capacity Pressure with percentiles 80 / 20 / 20 scores 44, while 80 / missing / missing scores 62. We prefer it to renormalising over the measured metrics, which would quietly let an airport's other strengths stand in for the gap. Imputation is always disclosed. An airport below 7 of 7 **Coverage** gets a **Provisional Score**, shown with its Coverage and the names of the imputed metrics, and an airport with no measured metric in a whole Pillar is listed as "not ranked: insufficient data".

**Data Confidence** is computed and never judged by the model. It is High at 7 of 7 Coverage, Medium at 5–6 of 7 or for any scenario, estimate or ad-hoc result, and Low at 4 or fewer, always with stated reasons. It describes the evidence, not the chance that an investment succeeds. The same Snapshot and the same weights produce byte-identical Ranking JSON, and a test checks it.

**Unmet Demand** (`unmet_demand`). No public source records passengers who were turned away, so the tool builds the answer in three labelled layers:

1. **Constraint Evidence (observed):** delay share and taxi-out against the national median, NAS delay per flight, the arrival-rate drop from good-weather (VFR) to bad-weather (IFR) runway capacity, the share of route-months with Load Factor above 0.85, and seat growth against passenger growth. A deterministic `why_drivers` list ranks these by strength.
2. **Forecast Gap:** the FAA TAF growth in enplanements and air-carrier operations, FY2024 → FY2030. For SFO that is +5.75M enplanements (+23.2%).
3. **Spill Scenario:** for full route-months, assumed spill rates of 2–5%, 5–10% and 10–15% by Load Factor band give a low–high range of passengers who *might* have been turned away. It is labelled "scenario under assumed spill rates; not calibrated" and never presented as the answer.

Every Unmet Demand answer also returns a fixed list of what the data cannot determine: actual turned-away passengers, demand recaptured by nearby airports, whether the binding constraint is the terminal, the gates or the runways, airline network choices, and project cost and revenue. Data Confidence is Medium by construction.

**Long-haul** (`route_mix`). A **Long-haul Flight** is a segment of 3,000 statute miles or more, a stated and overridable Assumption. The headline is the share of scheduled passenger departures. The passenger-weighted share and the cargo-inclusive share are always returned as labelled variants, because at a cargo hub they tell different stories. At Anchorage the figures are 2.7% of passenger departures, 6.2% of passengers, and 29.5% of all departures, with all-cargo flights making up 95.7% of the long-haul departures. The tool pre-computes these group totals so the model quotes them and never adds rows itself.

**Congestion lens** (`compare_airports`). Delays, taxi-out, cancellations, NAS delay, departures per runway per day and Load Factor with national percentiles, plus live FAA status. Its `congestion_index` is labelled as a lens, separate from the Investment Opportunity Score.

## 5. Where and how AI is used

The language model (Claude Sonnet 5.5, run by Pydantic AI) does four things:

- **Interprets the question and chooses tools.** It maps "New England" to six states, resolves "LA" to LAX through `resolve_airports` (and offers the alternates), and turns "growth matters twice as much" into a weight override.
- **Handles ambiguity openly.** It makes a reasonable Assumption, states it, and offers the alternative instead of asking a clarifying question first.
- **Explains.** It writes the answer in a fixed shape: a direct answer and table, the drivers, Assumptions and scope, then Data Confidence with As-of Dates, followed by suggested follow-ups.
- **Writes ad-hoc SQL** for questions the fixed tools don't cover, through `query_snapshot`. The SQL is parsed (SELECT/WITH only), runs on a read-only connection with a 200-row cap and a 5-second timeout, is shown in the Trace, and the answer is labelled ad hoc with Data Confidence at most Medium.

The model **never computes a score or invents a number**. Several mechanisms enforce that:

- **No arithmetic left to do.** Scores, percentiles, Coverage, Data Confidence, shares, totals and Forecast Gaps arrive pre-computed. The system prompt says to quote figures and never to add them. In the BOS-to-Europe example the model declined to sum two monthly counts itself because no tool had returned the total.
- **The envelope carries the caveats.** Assumptions, caveats and Data Confidence reasons come from the tools, and the prompt requires the answer to repeat them.
- **Number-grounding test.** A live test runs the six acceptance questions against real Claude and fails if any percentage or any number with three or more significant digits in the answer is missing from that run's tool results. This test caught a real defect: the model mis-grouped an 8-digit integer ("30,516426"). The fix formats large numbers before the model sees them, so it copies characters instead of formatting digits.
- **Scope.** The agent has no web, shell or write tools. Off-topic requests and attempts to override the prompt get a scoping statement.

The build itself was done by coding agents working from `docs/SPEC.md`, with these tests as the gate.

## 6. Key tradeoffs

**Snapshot plus Live Signals, rather than fully live (ADR 0001).** The brief asks for public APIs, but most of the metrics we need (route distances, delays, forecasts, enplanements) exist only as bulk downloads, some taking minutes per month. Scoring on a dated Snapshot makes every score reproducible and the demo independent of API uptime. Three keyless APIs (BTS traffic, DOT airfares, FAA NAS Status) are agent tools called at question time. They add fresh evidence to explanations but never change a score. The cost is staleness: the Snapshot ends Jul–Aug 2026 and must be rebuilt to move forward.

**Geometric mean of percentile Pillars, with median imputation (ADR 0002).** An arithmetic mean is easier to explain but lets a huge, stagnant airport rank high, which contradicts the thesis. Z-scores are distorted by aviation's extreme outliers. Median imputation was chosen over renormalisation because its bias has a known direction and is always disclosed.

**Proven harness instead of a custom agent loop (ADR 0003).** Pydantic AI runs the tool loop over plain Python functions, and its Vercel AI adapter streams tool steps to `useChat` with no custom glue. The Claude Agent SDK was rejected for a web app: it runs a subprocess per session, and its main value is built-in tools we would disable.

**Voice as a shell over the same agent (ADR 0004).** The planned voice mode delegates every analytic question to the same Claude agent and tools, so voice and text can never disagree on a number. It is designed but not built in this time box.

**Hosting and guards.** One container on a free Render service with Neon Postgres is simple and cheap, at the cost of a cold start after idle. A public demo on a paid model needs guards: an access code (10 failed tries per IP per hour), 30 messages per hour, a 2,000-character cap, at most 12 model requests per answer, and a $5 daily budget across all sessions, the hard stop if the code leaks.

**What we cut**, in favour of correctness and honest uncertainty: Evidence charts (the tables carry the same numbers), a live SoQL escape hatch over the public APIs, the voice call, a slide deck, and finer sources such as DB1B O&D tickets and FAA ASPM hourly capacity.

## 7. Limitations and next steps

- **The score screens; it does not prove profitability.** Proving profitability would need project cost estimates, terminal and gate utilisation (peak-hour passengers per gate and per square metre), commercial revenue (concessions, parking, airline rates and charges) and feasibility (land, environmental review, airline agreements, funding).
- **Percentiles reward small, fast-growing airports.** With growth weighted up, Block Island and Westerly enter the New England top 10 on Demand Momentum alone. Filtering by Hub Size, which the Ranking tool supports, is the remedy.
- **Delay and taxi-out cover only reporting carriers' domestic flights**, so international congestion is invisible, and airports below 1,000 such departures get Provisional Scores.
- **Runway capacity is hand-coded for four airports** (SFO, LAX, SNA, BOS) from 2014–2019 FAA profiles.
- **Load Factor is not spill.** Full aircraft can reflect airline pricing. The Spill Scenario is uncalibrated and stays a sensitivity.
- **T-100 counts segments** (each leg of a multi-stop flight), and TAF fiscal years run Oct–Sep.
- **The weights are judgement and have not been validated.** The natural next step is a backtest: score airports as of a past year and check whether the high scorers went on to need or fund terminal projects.
- **Model wording varies between runs.** Numbers are grounded, but tool choice for unusual phrasings can differ, so the live tests should run on every prompt change.

Next steps, in order: a backtest of the weights; gate and terminal utilisation data for the shortlisted airports; ASPM hourly capacity for every large hub; a scheduled Snapshot refresh; and then the deferred features (charts, live SoQL, voice).
