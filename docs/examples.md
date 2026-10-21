# Example transcripts: golden questions G1–G6

Recorded from one live run of `make test-live` (real Claude, model `anthropic:claude-sonnet-5-5`, Snapshot built 2026-10-21T18:32:22Z). Every number in each answer passed the number-grounding check: it appears in a tool result of the same run. G5 is a follow-up in the G1 conversation. Regenerate with `WRITE_EXAMPLES=1 make test-live`.

Total model cost of the six answers: $0.26.

## G1. Which airports in New England are strong candidates for terminal expansion?

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"]})`
- `suggest_followups({"questions": ["What if growth matters twice as much for New England airports?", "Show the unmet demand and constraint evidence for BOS", "Compare congestion at BOS, BDL and PVD"]})`

**Agent response**

**Answer**

New England is CT, ME, MA, NH, RI and VT. These are the top 10 of 16 ranked Primary Airports, ordered by Investment Opportunity Score at the default Pillar Weights.

| Rank | Airport | Hub Size | Score | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BOS (MA) | L | 73.1 | 50.2 | 86.1 | 95.3 | 7 of 7 |
| 2 | BGR (ME) | N | 72.4 | 85.7 | 75.9 | 53 | 7 of 7 |
| 3 | BTV (VT) | S | 71.9 | 69.4 | 82.8 | 60.4 | 7 of 7 |
| 4 | HVN (CT) | S | 69.9 | 91.1 | 56.2 | 68.1 | provisional, 5 of 7 |
| 5 | PWM (ME) | S | 64.8 | 64.3 | 60.8 | 72.6 | 7 of 7 |
| 6 | PVD (RI) | S | 62.8 | 65 | 51.8 | 81.6 | 7 of 7 |
| 7 | PSM (NH) | N | 60.1 | 57.9 | 64.6 | 56.4 | provisional, 5 of 7 |
| 8 | BDL (CT) | M | 57 | 41.2 | 59.8 | 83.5 | 7 of 7 |
| 9 | MVY (MA) | N | 54.7 | 82.1 | 57.7 | 28.4 | 7 of 7 |
| 10 | MHT (NH) | S | 52.2 | 61.5 | 35.7 | 76.3 | 7 of 7 |

BOS, BGR and BTV are the strongest candidates. The scores of BOS, BGR and BTV sit close together.

**Why**
- **BOS:** It has the highest Market Scale (95.3) and a high Capacity Pressure (86.1), so it is large and strained. Its Demand Momentum is only middling (50.2).
- **BGR:** It has high Demand Momentum (85.7) and good Capacity Pressure (75.9). Its Market Scale is modest (53), which fits a nonhub airport.
- **BTV:** It is balanced across the Pillars: Capacity Pressure 82.8, Demand Momentum 69.4 and Market Scale 60.4.
- **HVN:** It has the highest Demand Momentum in the group (91.1), but its Capacity Pressure is only 56.2. Two of its metrics are imputed, so treat its rank with caution.
- **Lower ranks:** BDL and MHT have large Market Scale but weak growth or pressure. For BDL, Demand Momentum is 41.2. For MHT, Capacity Pressure is 35.7.

**Assumptions & scope**
- Assumption: I used the default Pillar Weights (Demand Momentum 0.35, Capacity Pressure 0.40, Market Scale 0.25). I can re-run with other weights.
- The Investment Opportunity Score is a screening signal. It gives a candidate list, not proof that a terminal project would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- On-Time data covers only reporting carriers on domestic flights. Delay and taxi-out therefore say nothing about international operations.
- HVN and PSM have no delay or taxi-out measure because they have fewer than 1,000 reporting-carrier departures. Both metrics were imputed at the median, which pulls their Capacity Pressure toward the middle.
- The table shows 10 of the 16 ranked airports in scope.

**Data Confidence:** Medium.
- 8 of 10 listed airports have full Coverage (7 of 7).
- HVN and PSM are provisional at 5 of 7 (imputed delay_share and taxi_out).
- Sources and windows:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: actuals to FY2024, forecast to FY2035.
  - BTS T-100: Aug 2025–Jul 2026.
  - BTS On-Time: Sep 2025–Aug 2026.
  - Census population: Vintage 2025, as of Jul 1, 2025.

*13 s, $0.035*

---

## G2. Compare LA and Santa Ana airport congestion levels.

**Tool calls**

- `resolve_airports({"query": "LA"})`
- `resolve_airports({"query": "Santa Ana"})`
- `compare_airports({"iatas": ["LAX", "SNA"], "lens": "congestion"})`
- `live_delays({"iatas": ["LAX", "SNA"]})`
- `suggest_followups({"questions": ["How do LAX and SNA rank for terminal expansion (Investment Opportunity Score)?", "Does SNA show Unmet Demand and Constraint Evidence?", "Compare Demand Momentum for LAX and SNA"]})`

**Agent response**

**Answer**

LAX is more congested than SNA, but the gap is modest on delays and large on traffic density. The tool's congestion_index is 57.5 for LAX and 50.1 for SNA. Neither airport has an active delay or ground stop right now.

| Metric | LAX | SNA |
|---|---|---|
| Departures delayed ≥15 min | 20.6% (pctile 58.5) | 20.6% (pctile 56.8) |
| Average taxi-out | 18.2 min (pctile 68.5) | 16.1 min (pctile 38.2) |
| Cancelled departures | 1% (pctile 17.8) | 1.1% (pctile 20.3) |
| NAS delay per departure | 3 min (pctile 45.6) | 3.5 min (pctile 55.2) |
| Departures per month (all T-100 classes) | 22,265.6 (pctile 99) | 4283 (pctile 88.5) |
| Departures per runway per day | 182.9 (pctile 98.5) | 70.4 (pctile 90.7) |
| Load factor (class F) | 82.3% (pctile 90.5) | 79.8% (pctile 74.4) |
| Runways | 4 | 2 |
| congestion_index | 57.5 | 50.1 |

**Why**
- **Delays are the same.** Both airports have 20.6% of departures delayed 15+ minutes. SNA has slightly higher NAS delay per departure (3.5 min against 3 min).
- **LAX is worse on taxi-out.** Its taxi-out is 18.2 min against 16.1 min, which puts LAX at the 68.5th percentile and SNA at the 38.2nd. This is the main driver of the index gap.
- **LAX is much busier.** It has 182.9 departures per runway per day against 70.4 at SNA. It also has the higher load factor, 82.3% against 79.8%.
- **SNA is still busy for its size.** Its 70.4 departures per runway per day is at the 90.7th percentile nationally.
- **Live Signal.** The FAA NAS Status feed shows no active delay at either airport. LAX has a closure notice that applies only to non-scheduled transient general aviation, so airline operations are unaffected.

**Assumptions & scope**
- "LA" is taken as LAX (Los Angeles International). The alternatives were BUR, LGB, ONT and SNA. "Santa Ana" is SNA (John Wayne/Orange County).
- On-Time metrics cover only reporting carriers' domestic flights. They say nothing about international operations.
- The congestion_index is the mean national percentile of delay share, taxi-out and NAS delay. It is a congestion lens, not the Investment Opportunity Score.
- Percentiles are among FAA Primary Airports that have each metric.
- The live feed is a Live Signal and changes no score.

**Data Confidence:** High. Every compared metric is measured for both airports, and the live feed is real-time.
- T-100: Aug 2025–Jul 2026 (as of Jul 2026).
- On-Time: Sep 2025–Aug 2026 (as of Aug 2026).
- FAA NAS Status: as of Wed Oct 21 20:42:48 2026 GMT.

*12 s, $0.040*

---

## G3. What is the percentage of long haul flights out of Anchorage airport?

**Tool calls**

- `route_mix({"iata": "ANC"})`
- `suggest_followups({"questions": ["How does Anchorage's long-haul share compare with Memphis or Louisville?", "Which Alaska airports rank best for terminal expansion?", "What is Anchorage's Investment Opportunity Score?"]})`

**Agent response**

**Answer**

Long-haul Flight means a segment of 3,000 statute miles or more. At Anchorage (ANC), the share depends on which flights you count:

| Measure | Long-haul | Total | Share |
|---|---|---|---|
| (a) **Headline:** scheduled passenger departures (class F) | 1005 | 37,243 | **2.7%** |
| (b) Passenger-weighted (passengers on long-haul segments) | 166,414 | 2,699,637 | 6.2% |
| (c) Cargo-inclusive (all service classes) | 25,743 | 87,249 | 29.5% |

**Why**

ANC is a cargo hub, so the cargo-inclusive share is far above the passenger share.
- Non-passenger departures (classes G, L and P) are 57.3% of all departures. Of those 50,006 departures, 24,738 are long-haul (49.5%).
- All-cargo flights (classes G and P) make up 24,643 of the 25,743 long-haul departures. That is 95.7% of all long-haul departures. The all-cargo total is 47,717 departures, of which 51.6% are long-haul.
- By class:

| Class | Departures | Long-haul departures | Long-haul share | Share of all long-haul departures |
|---|---|---|---|---|
| F, scheduled passenger | 37,243 | 1005 | 2.7% | 3.9% |
| G, scheduled cargo | 33,824 | 16,234 | 48% | 63.1% |
| L, charter | 2289 | 95 | 4.2% | 0.4% |
| P, non-scheduled cargo/other | 13,893 | 8409 | 60.5% | 32.7% |

- Scheduled passenger (class F) flights are 42.7% of departures but only 3.9% of long-haul departures.
- The class F long-haul flights are mostly domestic. Examples are DFW (388 departures), ATL (156), IAH (128), IAD (110) and EWR (101). The longest international one listed is FRA (30 departures).
- The cargo long-haul flights are mainly freighters stopping between Asia and North America.

**Assumptions & scope**
- The window is the 12 months from Aug 2025 to Jul 2026.
- T-100 counts each leg of a multi-stop flight separately, so a multi-stop flight counts once per leg.
- Non-passenger means classes G, L and P. All-cargo means G and P, because L charters can carry passengers.
- The top-destinations list covers class F only.
- I took "long haul flights" to mean the passenger headline (a). The cargo-inclusive figure (c) is a separate variant.

**Data Confidence**

High. T-100 is a census of all carriers' segments, covering 12 months from Aug 2025 to Jul 2026. Source: BTS T-100 Segment (All Carriers), as of Jul 2026.

*14 s, $0.043*

---

## G4. What is the unmet flight demand in SFO airport and why?

**Tool calls**

- `unmet_demand({"iata": "SFO"})`
- `od_demand({"iata": "SFO"})`
- `suggest_followups({"questions": ["How does SFO's congestion compare with LAX and SEA?", "Are there any current ground stops or delays at SFO?", "Where does SFO rank among large hubs for terminal investment?"]})`

**Agent response**

**Answer**

The public data can't measure unmet demand at SFO directly, because no public source records turned-away passengers. SFO does show strong signs of constraint, and the FAA forecasts further growth.

- **Constraint Evidence (observed):** SFO is worse than the national median on delays, taxi-out time, load factor and the share of full routes.
- **Forecast Gap:** FAA TAF enplanements are forecast to rise from 24,765,642 in FY2024 to 30,516,426 in FY2030, which is +23.2%. Air-carrier operations are forecast to rise from 350,805 to 435,218, which is +24.1%.

**Why**

Drivers are listed in order of strength. Strength is SFO's national percentile on each indicator.

| Constraint Evidence | SFO | National median | Strength |
|---|---|---|---|
| Average taxi-out | 23 min | 16.8 min | 96.3 |
| Load factor (class F) | 82.1% | 75.8% | 89.4 |
| Departures delayed ≥15 min | 25.3% | 20% | 88.4 |
| Route-months with load factor above 0.85 | 35.2% | 18.6% | 83.4 |
| Arrival rate drop in bad weather (IFR 36/hr vs VFR 54/hr) | 33.3% | n/a | 66.7 |
| NAS delay per departure | 3.9 min | 3.3 min | 64.7 |

- Passenger growth of 0.6% against seat growth of 0.7% is about level. Passenger growth minus seat growth is -0.1 pp, against a national median of -0.9 pp. This is not a sign of supply falling behind demand.
- **Market side (DOT Consumer Airfare Report, 2026 Q1 Live Signal):** the busiest markets are:
  - LAX, with 4,717.5 passengers per day.
  - JFK, with 3,721.4 passengers per day and an average fare of $494.88.
  - EWR, with 2,941.4 passengers per day, an average fare of $571.70, and UA holding 86.1% of the market.
- Carrier concentration is high on some routes. UA holds 69.5% of SFO–ORD and 66.5% of SFO–DEN.

**Spill Scenario (a scenario under assumed spill rates, not calibrated and not observed)**

Applying assumed spill rates to class F route-months with load factor above 0.85 gives a range of 396,415 to 839,701. The routes that contribute most are EWR (12 months over the threshold), JFK (10), ORD (10), DFW (10) and HNL (9). Full aircraft alone do not prove that anyone was turned away.

**Assumptions & scope**

- Benchmarks are national medians of FAA Primary Airports.
- On-Time data covers only the largest reporting carriers and domestic flights. It says nothing about international operations.
- The airfare report covers only large domestic city-pair markets, from one quarter of a 10% ticket sample.
- The IFR/VFR rates come from the FAA's 2019 SFO capacity profile. The 2014 profile is no longer published.
- Live NAS status is a separate Live Signal. I did not pull it here.
- **What the data can't tell us:**
  - Actual denied or turned-away passengers.
  - Demand that went to nearby airports such as OAK or SJC.
  - Whether the binding constraint is the terminal, the gates or the runway and airspace.
  - Airline network choices versus infrastructure limits.
  - Project cost and revenue.

**Data Confidence: Medium**

- Unmet Demand is argued from observed indicators and an official forecast. Turned-away passengers are not observed in any public data.
- The Spill Scenario rests on assumed, uncalibrated spill rates.
- The airfare data comes from the DB1B 10% sample and covers one quarter.
- Windows:
  - T-100: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - TAF 2025: actuals to FY2024, forecast to FY2030.
  - Airfare report: 2026 Q1.
  - FAA capacity profile: 2019.

*14 s, $0.043*

---

## G5. What if growth matters twice as much?

*(Follow-up in the G1 conversation.)*

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"], "weights": {"momentum": 0.7, "pressure": 0.4, "scale": 0.25}})`
- `suggest_followups({"questions": ["Show the unmet demand and constraint evidence for BGR", "What if congestion matters twice as much for New England?", "Give the full scorecard for HVN"]})`

**Agent response**

**Answer**

I doubled the Demand Momentum weight and left the other weights at their defaults. The tool normalised the weights to Demand Momentum 0.52, Capacity Pressure 0.30 and Market Scale 0.19. The scope is the same: New England (CT, ME, MA, NH, RI, VT).

| New rank | Airport | Score | Demand Momentum | Capacity Pressure | Market Scale | Coverage | Previous rank |
|---|---|---|---|---|---|---|---|
| 1 | BGR | 75.6 | 85.7 | 75.9 | 53 | 7 of 7 | 2 |
| 2 | HVN | 74.8 | 91.1 | 56.2 | 68.1 | provisional, 5 of 7 | 4 |
| 3 | BTV | 71.3 | 69.4 | 82.8 | 60.4 | 7 of 7 | 3 |
| 4 | BOS | 66.4 | 50.2 | 86.1 | 95.3 | 7 of 7 | 1 |
| 5 | PWM | 64.7 | 64.3 | 60.8 | 72.6 | 7 of 7 | 5 |
| 6 | PVD | 63.4 | 65 | 51.8 | 81.6 | 7 of 7 | 6 |
| 7 | MVY | 60.8 | 82.1 | 57.7 | 28.4 | 7 of 7 | 9 |
| 8 | PSM | 59.5 | 57.9 | 64.6 | 56.4 | provisional, 5 of 7 | 7 |
| 9 | BID | 57.4 | 96.2 | 32.4 | 33.7 | provisional, 5 of 7 | not in the top 10 |
| 10 | WST | 57.4 | 96 | 32.7 | 33.3 | provisional, 5 of 7 | not in the top 10 |

**Why**
- **BGR** moves up to first. It has high Demand Momentum (85.7) and good Capacity Pressure (75.9).
- **HVN** moves up to second. Its Demand Momentum is the highest of the larger airports (91.1), but its Capacity Pressure is only 56.2.
- **BOS** falls from first to fourth. Its Demand Momentum is the weakest of the top five (50.2), so extra weight on growth penalises it, despite its Market Scale (95.3) and Capacity Pressure (86.1).
- **MVY** rises two places on its Demand Momentum of 82.1.
- **BDL and MHT** drop out of the top 10. BDL's Demand Momentum is 41.2 and MHT's Capacity Pressure is 35.7.
- **BID and WST** enter the top 10 at ranks 9 and 10. Both have very high Demand Momentum (96.2 and 96) but low Capacity Pressure (32.4 and 32.7) and low Market Scale (33.7 and 33.3). The scores of BID and WST are provisional, with imputed delay and taxi-out. Treat them as growth-driven results, not strain-driven ones.

**Assumptions & scope**
- Assumption: "growth matters twice as much" means Demand Momentum 0.70 against the defaults of 0.40 for Capacity Pressure and 0.25 for Market Scale. The tool normalised these weights. The alternative is to weight Capacity Pressure or Market Scale instead.
- The Investment Opportunity Score is a screening signal. It gives a candidate list, not proof that a terminal project would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- On-Time data covers only reporting carriers on domestic flights. Delay and taxi-out therefore say nothing about international operations.
- HVN, PSM, BID and WST have fewer than 1,000 reporting-carrier departures. Their delay share and taxi-out were imputed at the median.
- The table shows 10 of the 16 ranked airports in scope.

**Data Confidence:** Medium.
- 6 of 10 listed airports have full Coverage (7 of 7).
- HVN, PSM, BID and WST are provisional at 5 of 7 (imputed delay_share, taxi_out).
- Sources and windows:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: actuals to FY2024, forecast to FY2035.
  - BTS T-100: Aug 2025–Jul 2026.
  - BTS On-Time: Sep 2025–Aug 2026.
  - Census population: Vintage 2025, as of Jul 1, 2025.

*14 s, $0.065*

---

## G6. How many flights left BOS for Europe last summer?

**Tool calls**

- `query_snapshot` (long arguments)

  ```sql
  SELECT year, month, SUM(departures_performed) AS deps, SUM(CASE WHEN service_class='F' THEN departures_performed ELSE 0 END) AS f_deps FROM t100_routes WHERE origin='BOS' AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') GROUP BY year, month ORDER BY year, month
  ```

- `query_snapshot` (long arguments)

  ```sql
  SELECT year, month, SUM(departures_performed) AS deps, SUM(CASE WHEN service_class='F' THEN departures_performed ELSE 0 END) AS f_deps FROM t100_routes WHERE origin='BOS' AND year IN (2025,2026) AND month IN (6,7,8) AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') GROUP BY ROLLUP (year, month) ORDER BY year, month
  ```

- `suggest_followups({"questions": ["Which European cities had the most departures from BOS last summer?", "What is BOS's long-haul share of departures?", "How does BOS rank for terminal expansion in New England?"]})`

**Agent response**

**Answer**

In the most recent summer in the Snapshot, 2026, 2,886 flights left BOS for Europe. That covers June and July only, because August 2026 is not in the Snapshot yet. Of those, 2,872 were scheduled passenger flights (class F). This is an ad hoc result.

| Summer | Month | All flights | Scheduled passenger (F) |
|---|---|---|---|
| 2026 | Jun | 1,432 | 1,425 |
| 2026 | Jul | 1,454 | 1,447 |
| **2026 (Jun–Jul only)** | **Total** | **2,886** | **2,872** |
| 2025 (full summer) | Jun | 1,432 | 1,423 |
| 2025 (full summer) | Jul | 1,480 | 1,471 |
| 2025 (full summer) | Aug | 1,485 | 1,466 |
| **2025 (Jun–Aug)** | **Total** | **4,397** | **4,360** |

**Why**

- I used the departures-performed count in the Snapshot's BTS T-100 route table, for flights originating at BOS with a destination in Europe.
- The 2025 summer is the latest complete June–August, so I included it for a like-for-like view.
- Comparing only June and July, 2026 is close to 2025. June is 1,432 in both years, and July is 1,454 against 1,480.

**Assumptions & scope**

- "Last summer" means June–August of the most recent year. For 2026 I used the months the Snapshot has, and August is missing.
- "Flights" means all T-100 service classes, which includes a small number of non-scheduled and cargo flights. The class F column is the passenger-only view.
- Europe uses the standard country list, with Turkey excluded.
- These are segment departures performed, with all carriers combined.

**Data Confidence**

Medium, because this is an ad hoc query outside the scoring methodology. The source is BTS T-100 Segment (All Carriers), with an As-of Date of Jul 2026 and a 24-month window from Aug 2024 to Jul 2026.

*15 s, $0.038*
