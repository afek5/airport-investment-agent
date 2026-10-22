# Design: Airport Investment Intelligence Agent

## 1. Problem and Investment Thesis

An investor in US airport modernisation wants an agent that finds airports where a terminal renovation is most likely to pay off through added capacity. No public dataset measures renovation profitability, so the agent works from an explicit **Investment Thesis**: a renovation is most promising where demand is growing, the infrastructure is already strained by that demand, and the market is large enough to monetise new capacity. Those clauses become the three **Pillars** of a deterministic **Investment Opportunity Score**: Demand Momentum, Capacity Pressure and Market Scale.

The score is a **screening signal**: it shows which airports deserve a closer look, not that a renovation would be profitable. Every Ranking says so.

## 2. Architecture

```
 Browser: Next.js chat (Vercel AI SDK useChat) + Mission panel: Progress·Evidence·Trace
    │  POST /api/chat  (UI-message stream: text, tool calls, tool results)
    ▼
 FastAPI ── guards: access code · 30 msgs/h · $5/day · 2,000 chars · 12 requests/answer
    ▼
 Pydantic AI agent (Claude Sonnet 5.5) ── chooses tools, explains, never computes
    ├── deterministic tools ──► DuckDB (read-only) ──► Snapshot (Parquet + manifest)
    │     resolve_airports · rank_airports · airport_scorecard · compare_airports
    │     route_mix · unmet_demand · query_snapshot (read-only SQL)
    ├── Live Signals ──► BTS SODA · DOT Airfare SODA · FAA NAS Status
    │     live_traffic · od_demand · live_delays · query_public_api (whitelisted SoQL)
    └── suggest_followups              Postgres: sessions, history, usage and cost
 Offline: ingest/ scripts ──► FAA / BTS / Census downloads ──► data/snapshot/
```

One container serves API and frontend. Every tool returns one envelope (`data`, `sources` with As-of Dates, `assumptions`, `data_confidence`, `coverage`, `caveats`, `ad_hoc`), and the Evidence panel shows each tool's `data` as a table, so every figure in an answer can be checked. Charts above the tables plot the same tool fields: Pillar bars on the Ranking, a Pillar chart on the scorecard, and route-mix donuts.

## 3. Data

All scoring runs on the **Snapshot**: Parquet tables built by script from public sources and committed, with a manifest of sources, months and row counts.

| Table | Source | As-of / window | Feeds |
|---|---|---|---|
| `airports` (402 Primary Airports) | FAA CY2025 commercial-service list, OurAirports, Census Geocoder | CY2025 | universe, Hub Size, runways, metro |
| `enplanements` | FAA commercial-service enplanements | CY2024–CY2025 | growth, market size |
| `taf` | FAA Terminal Area Forecast 2025 | FY2015–FY2045 | forecast growth, Forecast Gap |
| `t100_routes` | BTS T-100 Segment, all carriers | Aug 2024–Jul 2026 | Load Factor, route mix, Spill |
| `ontime_airport_month` | BTS Reporting Carrier On-Time | Sep 2025–Aug 2026 | delays, taxi-out, cancellations |
| `metro_population` | Census Population Estimates, V2025 | Jul 1, 2025 | metro population |
| `runway_capacity` | FAA Capacity Profiles, hand-coded | 2014–2019 | bad-weather capacity drop |

Live Signals, fetched at question time: BTS traffic (SODA `r495-tyji`), DOT Airfare Report (SODA `tfrh-tu9e`), FAA NAS Status. `query_public_api` runs ad-hoc SoQL on those two BTS/DOT datasets and the DOT city-pair table (`yj5y-b2ir`), for fare or market history the Snapshot lacks.

## 4. Scoring methodology

**Percentiles.** Each of seven metrics becomes a **Percentile Score** across the 402 Primary Airports (`rank(pct=True) × 100`), so a 2M-passenger airport compares with a 40M one, outliers cannot stretch the scale, and enplanements need no log transform (a rank is the same before and after one).

| Pillar (default weight) | Metric (weight in Pillar) |
|---|---|
| **Demand Momentum** (0.35) | TAF enplanement CAGR FY2024 → FY2035 (0.60); enplanement growth CY2024 → CY2025 (0.40) |
| **Capacity Pressure** (0.40) | Load Factor, last 12 T-100 months (0.40); share of departures delayed ≥ 15 min (0.30); average taxi-out (0.30) |
| **Market Scale** (0.25) | CY2025 enplanements (0.70); 2025 metro (CBSA) population (0.30) |

Capacity Pressure weighs most because expansion pays when demand already presses on infrastructure; Market Scale least, because it bounds value without creating need. The weights are a judgement an analyst can override in conversation.

**Pillar score** = weighted mean of its metric percentiles. **Investment Opportunity Score** = `exp(Σ w_p · ln(max(pillar_p, 1)))`, a weighted geometric mean on a 1–100 scale. The thesis is a conjunction, so a weak Pillar should hurt more than an arithmetic mean lets it: Martha's Vineyard (Pillars 82.1 / 57.7 / 28.4) scores 54.7, against 58.9 arithmetic.

**Missing data.** Delay share and taxi-out are null below 1,000 reporting-carrier departures, and metro population is null outside a metro or micro area. A missing metric is **imputed at the median (50)**, which pulls the Pillar toward the middle (80 / 20 / 20 scores 44; 80 / missing / missing scores 62). Renormalising instead would quietly let an airport's other strengths stand in for the gap. An airport below 7 of 7 **Coverage** gets a **Provisional Score** naming the imputed metrics; one with no measured metric in a whole Pillar is "not ranked: insufficient data".

**Data Confidence** is computed, never judged by the model: High at 7 of 7 Coverage, Medium at 5–6 or for any scenario or ad-hoc result, Low at 4 or fewer, always with reasons. It rates the evidence, not the investment. A test checks that the same Snapshot and weights give byte-identical Ranking JSON.

**Unmet Demand** (`unmet_demand`). No public source records turned-away passengers, so the tool answers in three labelled layers: **Constraint Evidence** (observed delays, taxi-out, NAS delay, bad-weather runway capacity drop, route-months above 0.85 Load Factor, seat vs passenger growth); the **Forecast Gap** from the FAA TAF, FY2024 → FY2030 (SFO: +5.75M enplanements, +23.2%); and a **Spill Scenario** from assumed spill rates by Load Factor band, labelled "not calibrated". It also lists what the data cannot determine (recapture by nearby airports, whether terminal, gates or runways bind). Data Confidence is Medium.

**Long-haul** (`route_mix`): segments of 3,000 statute miles or more, an overridable Assumption, as shares of passenger departures, passengers and all departures (Anchorage: 2.7%, 6.2%, 29.5%). **Congestion** (`compare_airports`) is a separate lens, never part of the score.

## 5. Where and how AI is used

The language model (Claude Sonnet 5.5, run by Pydantic AI):

- **Interprets the question and chooses tools.** It maps "New England" to six states, resolves "LA" to LAX through `resolve_airports`, and turns "growth matters twice as much" into a weight override.
- **Handles ambiguity openly**, stating an Assumption and offering the alternative, then **explains** in a fixed shape: answer and table, drivers, Assumptions, Data Confidence with As-of Dates.
- **Writes ad-hoc queries** when no fixed tool fits: read-only SQL over the Snapshot through `query_snapshot` (SELECT/WITH only, 200 rows, 5 seconds), or, last, live SoQL through `query_public_api` (three whitelisted datasets, clause bodies only, at most 500 rows). Both are shown in the Trace and labelled ad hoc with Data Confidence at most Medium.

The model **never computes a score or invents a number**:

- **No arithmetic left to do.** Scores, percentiles, shares, totals and Forecast Gaps arrive pre-computed, and the prompt says to quote, never add. Assumptions and caveats come from the tool envelope.
- **Number-grounding test.** A live test runs the six acceptance questions against real Claude and fails if any percentage or 3+-significant-digit number is missing from that run's tool results. It caught the model mis-grouping "30,516426"; large numbers are now pre-formatted for it to copy.
- **Scope.** No web, shell or write tools; off-topic and prompt-override requests get a scoping statement.

## 6. Key tradeoffs

**Snapshot plus Live Signals, not fully live (ADR 0001).** Most metrics exist only as bulk downloads. A dated Snapshot makes scores reproducible and the demo independent of API uptime; Live Signals add evidence but never change a score. The cost is staleness.

**Geometric mean of percentiles, median imputation (ADR 0002).** An arithmetic mean lets a huge, stagnant airport rank high, contradicting the thesis; z-scores are distorted by aviation's outliers. Median imputation's bias has a known direction and is always disclosed.

**Proven harness, not a custom loop (ADR 0003).** Pydantic AI runs the tool loop over plain functions, and its Vercel AI adapter streams tool steps to `useChat` with no glue. The Claude Agent SDK runs a subprocess per session for built-in tools we would disable.

**Voice as a shell over the same agent (ADR 0004)**, so voice cannot disagree with text on a number. Designed, not built.

**Hosting and guards.** Delivered local-only (`docker compose up` with the reviewer's own key). A free Render blueprint (web service plus Render Postgres) is prepared: cheap but cold-starts; the guards above (and 10 failed access codes per IP per hour) are built for a public demo on a paid model. **Cut:** the voice call, DB1B and ASPM data. A 5-slide deck is in `docs/deck.pptx`.

## 7. Limitations and next steps

- **The score screens; it does not prove profitability.** That needs project cost, gate utilisation, commercial revenue and feasibility.
- **Percentiles reward small, fast-growing airports**: with growth weighted up, Block Island enters the New England top 10. Filter by Hub Size.
- **Delay data covers only reporting carriers' domestic flights**; runway capacity is hand-coded for four airports; Load Factor is not spill.
- **The weights are unvalidated**, and model wording varies between runs, so live tests should run on every prompt change.

Next steps: backtest the weights against past terminal projects; add gate utilisation and ASPM data; schedule Snapshot refreshes.
