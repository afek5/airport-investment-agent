# Example transcripts: golden questions G1–G6

Recorded from one live run of `make test-live` (real Claude, model `anthropic:claude-sonnet-5-5`, Snapshot built 2026-10-21T18:32:22Z). Every number in each answer passed the number-grounding check: it appears in a tool result of the same run. G5 is a follow-up in the G1 conversation. Regenerate with `WRITE_EXAMPLES=1 make test-live`.

Total model cost of the six answers: $0.27.

## G1. Which airports in New England are strong candidates for terminal expansion?

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"]})`
- `suggest_followups({"questions": ["What if growth matters twice as much for New England airports?", "Compare congestion at BOS, BTV and BGR", "What unmet demand is there at Burlington (BTV)?"]})`

**Agent response**

**Answer**

Assumption: New England means CT, ME, MA, NH, RI and VT, ranked on the default Pillar Weights. The table shows the top 10 of 16 ranked airports.

| Rank | Airport | Hub Size | Investment Opportunity Score | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BOS Boston Logan (MA) | L | 73.1 | 50.2 | 86.1 | 95.3 | 7 of 7 |
| 2 | BGR Bangor (ME) | N | 72.4 | 85.7 | 75.9 | 53 | 7 of 7 |
| 3 | BTV Burlington (VT) | S | 71.9 | 69.4 | 82.8 | 60.4 | 7 of 7 |
| 4 | HVN New Haven (CT) | S | 69.9 | 91.1 | 56.2 | 68.1 | provisional, 5 of 7 |
| 5 | PWM Portland (ME) | S | 64.8 | 64.3 | 60.8 | 72.6 | 7 of 7 |
| 6 | PVD Providence (RI) | S | 62.8 | 65 | 51.8 | 81.6 | 7 of 7 |
| 7 | PSM Portsmouth (NH) | N | 60.1 | 57.9 | 64.6 | 56.4 | provisional, 5 of 7 |
| 8 | BDL Bradley (CT) | M | 57 | 41.2 | 59.8 | 83.5 | 7 of 7 |
| 9 | MVY Martha's Vineyard (MA) | N | 54.7 | 82.1 | 57.7 | 28.4 | 7 of 7 |
| 10 | MHT Manchester (NH) | S | 52.2 | 61.5 | 35.7 | 76.3 | 7 of 7 |

The strongest candidates to investigate first are BOS, BGR and BTV. Their scores are close together.

**Why**

- **BOS (73.1):** It has the highest Market Scale (95.3) and a high Capacity Pressure (86.1). Its Demand Momentum is only mid-range (50.2), so growth is the weakest of its three Pillars.
- **BGR (72.4):** It has the second-highest Demand Momentum in the group (85.7) and solid Capacity Pressure (75.9). Its Market Scale is moderate (53) because it is a nonhub airport.
- **BTV (71.9):** Its Capacity Pressure (82.8) is second only to BOS. Its Demand Momentum (69.4) and Market Scale (60.4) are both decent.
- **HVN (69.9):** It has the highest Demand Momentum in the list (91.1). Its Capacity Pressure is only 56.2, and that Pillar rests on imputed data.
- **Lower ranks:** BDL and PVD have large Market Scale (83.5 and 81.6) but weaker Capacity Pressure and growth. MHT has the lowest Capacity Pressure in the top 10 (35.7).

**Assumptions & scope**

- This is a screening list of airports worth investigating. It is not proof that an expansion would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- HVN and PSM have a Provisional Score. Delay share and taxi-out were imputed at the median because each has fewer than 1,000 reporting-carrier departures. This pulls their Capacity Pressure toward the middle.
- On-Time data covers only the largest US reporting carriers and domestic flights. Delay and taxi-out say nothing about international operations.
- Six ranked airports in scope are not shown. I can list them or re-rank with different Pillar Weights.

**Data Confidence:** Medium.
- 8 of 10 listed airports have full Coverage (7 of 7). HVN and PSM are provisional at 5 of 7.
- Sources and windows:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: FY2024 actual to FY2035 forecast.
  - BTS T-100: Aug 2025–Jul 2026.
  - BTS On-Time: Sep 2025–Aug 2026.
  - Census population: Jul 1, 2025 estimate.

**Answer**

Assumption: New England means CT, ME, MA, NH, RI and VT, ranked on the default Pillar Weights. The table shows the top 10 of 16 ranked airports.

| Rank | Airport | Hub Size | Investment Opportunity Score | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BOS Boston Logan (MA) | L | 73.1 | 50.2 | 86.1 | 95.3 | 7 of 7 |
| 2 | BGR Bangor (ME) | N | 72.4 | 85.7 | 75.9 | 53 | 7 of 7 |
| 3 | BTV Burlington (VT) | S | 71.9 | 69.4 | 82.8 | 60.4 | 7 of 7 |
| 4 | HVN New Haven (CT) | S | 69.9 | 91.1 | 56.2 | 68.1 | provisional, 5 of 7 |
| 5 | PWM Portland (ME) | S | 64.8 | 64.3 | 60.8 | 72.6 | 7 of 7 |
| 6 | PVD Providence (RI) | S | 62.8 | 65 | 51.8 | 81.6 | 7 of 7 |
| 7 | PSM Portsmouth (NH) | N | 60.1 | 57.9 | 64.6 | 56.4 | provisional, 5 of 7 |
| 8 | BDL Bradley (CT) | M | 57 | 41.2 | 59.8 | 83.5 | 7 of 7 |
| 9 | MVY Martha's Vineyard (MA) | N | 54.7 | 82.1 | 57.7 | 28.4 | 7 of 7 |
| 10 | MHT Manchester (NH) | S | 52.2 | 61.5 | 35.7 | 76.3 | 7 of 7 |

The strongest candidates to investigate first are BOS, BGR and BTV. Their scores are close together.

**Why**

- **BOS (73.1):** It has the highest Market Scale (95.3) and a high Capacity Pressure (86.1). Its Demand Momentum is only mid-range (50.2), so growth is the weakest of its three Pillars.
- **BGR (72.4):** It has the second-highest Demand Momentum in the group (85.7) and solid Capacity Pressure (75.9). Its Market Scale is moderate (53) because it is a nonhub airport.
- **BTV (71.9):** Its Capacity Pressure (82.8) is second only to BOS. Its Demand Momentum (69.4) and Market Scale (60.4) are both decent.
- **HVN (69.9):** It has the highest Demand Momentum in the list (91.1). Its Capacity Pressure is only 56.2, and that Pillar rests on imputed data.
- **Lower ranks:** BDL and PVD have large Market Scale (83.5 and 81.6) but weaker Capacity Pressure and growth. MHT has the lowest Capacity Pressure in the top 10 (35.7).

**Assumptions & scope**

- This is a screening list of airports worth investigating. It is not proof that an expansion would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- HVN and PSM have a Provisional Score. Delay share and taxi-out were imputed at the median because each has fewer than 1,000 reporting-carrier departures. This pulls their Capacity Pressure toward the middle.
- On-Time data covers only the largest US reporting carriers and domestic flights. Delay and taxi-out say nothing about international operations.
- Six ranked airports in scope are not shown. I can list them or re-rank with different Pillar Weights.

**Data Confidence:** Medium.
- 8 of 10 listed airports have full Coverage (7 of 7). HVN and PSM are provisional at 5 of 7.
- Sources and windows:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: FY2024 actual to FY2035 forecast.
  - BTS T-100: Aug 2025–Jul 2026.
  - BTS On-Time: Sep 2025–Aug 2026.
  - Census population: Jul 1, 2025 estimate.

*20 s, $0.053*

---

## G2. Compare LA and Santa Ana airport congestion levels.

**Tool calls**

- `resolve_airports({"query": "LA"})`
- `resolve_airports({"query": "Santa Ana"})`
- `compare_airports({"iatas": ["LAX", "SNA"], "lens": "congestion"})`
- `live_delays({"iatas": ["LAX", "SNA"]})`
- `suggest_followups({"questions": ["Which of LAX and SNA scores higher as a terminal expansion candidate?", "How much unmet demand is there at SNA?", "Compare congestion at LAX with BUR, LGB and ONT"]})`

**Agent response**

**Answer**

LAX is more congested than SNA overall, mainly on taxi-out time and runway intensity. Delay share is identical. The tool's congestion_index is 57.5 for LAX and 50.1 for SNA. Neither airport has an active delay or ground stop right now.

| Metric | LAX | SNA |
|---|---|---|
| Departures delayed ≥15 min | 20.6% (pctile 58.5) | 20.6% (pctile 56.8) |
| Average taxi-out | 18.2 min (68.5) | 16.1 min (38.2) |
| Cancelled departures | 1% (17.8) | 1.1% (20.3) |
| NAS delay per departure | 3 min (45.6) | 3.5 min (55.2) |
| Departures per month (all T-100 classes) | 22,265.6 (99) | 4283 (88.5) |
| Departures per runway per day | 182.9 (98.5) | 70.4 (90.7) |
| Load factor (class F) | 82.3% (90.5) | 79.8% (74.4) |
| Runways | 4 | 2 |
| **congestion_index** | **57.5** | **50.1** |

**Why**
- Delay share is the same at both airports (20.6%).
- LAX's taxi-out is longer, at 18.2 min against 16.1 min. Its percentile is 68.5 against 38.2.
- LAX handles 182.9 departures per runway per day. SNA handles 70.4, which is still high at the 90.7th percentile.
- LAX's load factor is higher (82.3% against 79.8%).
- SNA is slightly worse on NAS delay per departure (3.5 min against 3 min) and on cancellations (1.1% against 1%). The gaps are small.
- Live Signal (as of Wed Oct 21 20:26:32 2026 GMT): neither airport has an active delay. LAX has a closure notice that applies only to non-scheduled transient general aviation. Airline operations are not affected. Live Signals do not change any score.

**Assumptions & scope**
- "LA" = LAX (Los Angeles International). The alternates were BUR, LGB, ONT and SNA. "Santa Ana" = SNA (John Wayne/Orange County).
- National percentiles are among the FAA Primary Airports that have each metric.
- On-Time metrics are flight-weighted over the reporting carriers' departures. They cover domestic flights only and say nothing about international operations.
- Departures per month and per runway per day use all T-100 service classes and the OurAirports runway count.
- congestion_index is the mean national percentile of delay share, taxi-out and NAS delay per departure. It is a congestion lens, not the Investment Opportunity Score.

**Data Confidence**
- High. Every compared metric is measured for both airports. The live feed is real-time FAA NAS Status.
- T-100 window: 12 months, Aug 2025–Jul 2026.
- On-Time window: 12 months, Sep 2025–Aug 2026.
- Enplanements: CY2025. Live delays: as of Wed Oct 21 20:26:32 2026 GMT.

*11 s, $0.039*

---

## G3. What is the percentage of long haul flights out of Anchorage airport?

**Tool calls**

- `route_mix({"iata": "ANC"})`
- `suggest_followups({"questions": ["How does Anchorage score as an investment opportunity?", "Compare long-haul share at ANC with SEA and SFO", "How many passenger flights from Anchorage go to Asia or Europe?"]})`

**Agent response**

**Answer**

Long-haul Flight means a segment of 3,000 statute miles or more. At Anchorage (ANC) the share depends on which flights you count:

| Measure | Long-haul | Total | Share |
|---|---|---|---|
| (a) **Headline:** scheduled passenger departures (class F) | 1005 | 37,243 | **2.7%** |
| (b) Passenger-weighted (passengers on long-haul segments / all class F passengers) | 166,414 | 2,699,637 | 6.2% |
| (c) Cargo-inclusive (all service classes) | 25,743 | 87,249 | 29.5% |

**Why**

- **ANC is a cargo hub.** Non-passenger flights are 57.3% of all departures.
- **Cargo flights make up almost all long-haul departures.** All-cargo departures (classes G + P) account for 24,643 of the 25,743 long-haul departures, which is 95.7%. That is why the cargo-inclusive share (29.5%) is far above the passenger share (2.7%). The freighters are mostly stopping between Asia and North America.
- **By service class:**

| Class | Departures | Long-haul departures | Long-haul share |
|---|---|---|---|
| F (scheduled passenger) | 37,243 | 1005 | 2.7% |
| G (scheduled cargo) | 33,824 | 16,234 | 48% |
| L (charter) | 2289 | 95 | 4.2% |
| P (non-scheduled cargo) | 13,893 | 8409 | 60.5% |

- **Passenger long-haul flying is mostly domestic.** Dallas/Fort Worth (DFW) has 388 departures, Atlanta (ATL) 156, Houston Intercontinental (IAH) 128, and Washington Dulles (IAD) 110. Frankfurt (FRA) has 30, Tokyo Haneda (HND) 6 and Seoul Incheon (ICN) 2.
- **The passenger-weighted share is higher than the headline.** The 6.2% is higher than 2.7%, so long-haul passenger flights carry more passengers per flight than the average ANC passenger flight.

**Assumptions & scope**

- The headline counts scheduled passenger flights (class F) only, as departures performed from ANC.
- Non-passenger flights are classes G, L and P. All-cargo is G and P, because L charters can carry passengers.
- T-100 reports flight segments, so a multi-stop flight counts each leg separately.
- Zero-departure rows are dropped, and carriers and aircraft types are aggregated.
- The top-destinations list covers class F only.

**Data Confidence:** High. T-100 is a census of all carriers' segments. Source: BTS T-100 Segment (All Carriers), As-of Date Jul 2026, window 12 months, Aug 2025–Jul 2026.

Long-haul Flight means a segment of 3,000 statute miles or more. The share at Anchorage (ANC) depends on which flights you count.

**Answer**

| Measure | Long-haul | Total | Share |
|---|---|---|---|
| (a) **Headline:** scheduled passenger departures (class F) | 1005 | 37,243 | **2.7%** |
| (b) Passenger-weighted (passengers on long-haul segments / all class F passengers) | 166,414 | 2,699,637 | 6.2% |
| (c) Cargo-inclusive (all service classes) | 25,743 | 87,249 | 29.5% |

**Why**

- **ANC is a cargo hub.** Non-passenger flights are 57.3% of all departures.
- **Cargo flights make up almost all long-haul departures.** All-cargo departures (classes G + P) account for 24,643 of the 25,743 long-haul departures, which is 95.7%. That is why the cargo-inclusive share (29.5%) is far above the passenger share (2.7%). The freighters are mostly stopping between Asia and North America.
- **By service class:**

| Class | Departures | Long-haul departures | Long-haul share |
|---|---|---|---|
| F (scheduled passenger) | 37,243 | 1005 | 2.7% |
| G (scheduled cargo) | 33,824 | 16,234 | 48% |
| L (charter) | 2289 | 95 | 4.2% |
| P (non-scheduled cargo) | 13,893 | 8409 | 60.5% |

- **Passenger long-haul flying is mostly domestic.** Dallas/Fort Worth (DFW) has 388 departures, Atlanta (ATL) 156, Houston Intercontinental (IAH) 128, and Washington Dulles (IAD) 110. Frankfurt (FRA) has 30, Tokyo Haneda (HND) 6 and Seoul Incheon (ICN) 2.
- **The passenger-weighted share is higher than the headline.** The 6.2% is higher than 2.7%, so long-haul passenger flights carry more passengers per flight than the average ANC passenger flight.

**Assumptions & scope**

- The headline counts scheduled passenger flights (class F) only, as departures performed from ANC.
- Non-passenger flights are classes G, L and P. All-cargo is G and P, because L charters can carry passengers.
- T-100 reports flight segments, so a multi-stop flight counts each leg separately.
- Zero-departure rows are dropped, and carriers and aircraft types are aggregated.
- The top-destinations list covers class F only.

**Data Confidence:** High. T-100 is a census of all carriers' segments. Source: BTS T-100 Segment (All Carriers), As-of Date Jul 2026, window 12 months, Aug 2025–Jul 2026.

*14 s, $0.037*

---

## G4. What is the unmet flight demand in SFO airport and why?

**Tool calls**

- `unmet_demand({"iata": "SFO"})`
- `od_demand({"iata": "SFO"})`
- `suggest_followups({"questions": ["How does SFO's congestion compare with LAX and SEA?", "Is SFO a strong terminal-expansion candidate on the Investment Opportunity Score?", "Are there any ground stops or delays at SFO right now?"]})`

**Agent response**

**Answer**

The data can't measure SFO's unmet demand directly, because no public data records turned-away passengers. The observed Constraint Evidence shows an airport under strain, and the FAA forecast shows growth still to come.

- **Constraint Evidence:** SFO is worse than the national median on delays, taxi-out, load factor and full route-months.
- **Forecast Gap (FAA TAF, FY2024 → FY2030):** Enplanements rise from 24,765,642 to 30,516,426, which is 5,750,784 more, or 23.2%. Air-carrier operations rise from 350,805 to 435,218, which is 84,413 more, or 24.1%.

**Why**

The drivers are listed from strongest to weakest, with the national percentile on each.

| Indicator | SFO | National median | Percentile |
|---|---|---|---|
| Average taxi-out | 23 min | 16.8 min | 96.3 |
| Load Factor, class F | 82.1% | 75.8% | 89.4 |
| Departures delayed ≥15 min | 25.3% | 20% | 88.4 |
| Route-months with Load Factor above 0.85 | 35.2% | 18.6% | 83.4 |
| NAS delay per departure | 3.9 min | 3.3 min | 64.7 |

- **Bad-weather capacity:** The arrival rate falls 33.3%, from 54/hr in visual conditions to 36/hr in instrument conditions (FAA 2019 profile). Any low cloud therefore cuts capacity sharply.
- **Supply versus demand:** Passenger growth is 0.6% and seat growth is 0.7%. Passenger growth minus seat growth is -0.1 pp, against a national median of -0.9 pp. This is not a sign that supply is falling behind demand.
- **Market side (DOT Q1 2026, domestic):** The busiest markets are these.

| Market | Passengers per day | Average fare | Largest carrier share |
|---|---|---|---|
| LAX | 4,717.5 | $172.46 | UA, 33.5% |
| JFK | 3,721.4 | $494.88 | DL, 43.6% |
| EWR | 2,941.4 | $571.70 | UA, 86.1% |

  Long-distance markets such as EWR (UA 86.1%) and ORD (UA 69.5%) have high fares and a dominant carrier. That fits tight supply, but it doesn't prove it.

**Spill Scenario** (a scenario under assumed spill rates, not calibrated and not observed)
- If the Spill Scenario's assumed rates applied, they would give a range of 396,415 to 839,701 passengers. This is a sensitivity only.
- The routes contributing most are EWR (12 months over the threshold), JFK (10), ORD (10), DFW (10) and HNL (9).

**Assumptions & scope**
- Benchmarks are national medians of Primary Airports.
- On-Time data covers only large reporting carriers and domestic flights. Delay and taxi-out say nothing about international operations.
- The O&D data is one quarter of the DB1B 10% sample, covers domestic contiguous-US markets only, and is a Live Signal that doesn't change any score.
- The Spill Scenario rates are illustrative assumptions. Full aircraft alone don't prove that passengers were turned away.
- **What the data can't tell us:**
  - Actual denied or turned-away passengers.
  - Demand recaptured at nearby airports such as OAK and SJC.
  - Whether the binding constraint is the terminal, the gates or the runway and airspace.
  - Airline network choices versus infrastructure limits.
  - Project cost and revenue.

**Data Confidence: Medium**
- Unmet Demand is argued from observed indicators and an official forecast. Turned-away passengers are not observed in any public data.
- The Spill Scenario rests on assumed, uncalibrated rates.
- The O&D data comes from a 10% ticket sample covering one quarter.
- **Windows:**
  - T-100: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA TAF 2025: FY2024 actual → FY2030 forecast.
  - FAA capacity profile: 2019.
  - DOT fares: 2026 Q1.

*14 s, $0.044*

---

## G5. What if growth matters twice as much?

*(Follow-up in the G1 conversation.)*

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"], "weights": {"momentum": 0.7, "pressure": 0.4, "scale": 0.25}})`
- `suggest_followups({"questions": ["What if congestion matters twice as much instead?", "Show the Burlington (BTV) scorecard in detail", "Compare demand growth at BGR, HVN and BTV"]})`

**Agent response**

**Answer**

Assumption: "growth matters twice as much" means Demand Momentum is doubled to 0.70, with Capacity Pressure at 0.40 and Market Scale at 0.25. The tool normalised these to Demand Momentum 0.52, Capacity Pressure 0.30 and Market Scale 0.19. The scope is the same six New England states. The table shows the top 10 of 16 ranked airports.

| New rank | Airport | Score (new weights) | Default rank and score | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BGR Bangor | 75.6 | 2 (72.4) | 85.7 | 75.9 | 53 | 7 of 7 |
| 2 | HVN New Haven | 74.8 | 4 (69.9) | 91.1 | 56.2 | 68.1 | provisional, 5 of 7 |
| 3 | BTV Burlington | 71.3 | 3 (71.9) | 69.4 | 82.8 | 60.4 | 7 of 7 |
| 4 | BOS Boston Logan | 66.4 | 1 (73.1) | 50.2 | 86.1 | 95.3 | 7 of 7 |
| 5 | PWM Portland | 64.7 | 5 (64.8) | 64.3 | 60.8 | 72.6 | 7 of 7 |
| 6 | PVD Providence | 63.4 | 6 (62.8) | 65 | 51.8 | 81.6 | 7 of 7 |
| 7 | MVY Martha's Vineyard | 60.8 | 9 (54.7) | 82.1 | 57.7 | 28.4 | 7 of 7 |
| 8 | PSM Portsmouth | 59.5 | 7 (60.1) | 57.9 | 64.6 | 56.4 | provisional, 5 of 7 |
| 9 | BID Block Island | 57.4 | not in default top 10 | 96.2 | 32.4 | 33.7 | provisional, 5 of 7 |
| 10 | WST Westerly | 57.4 | not in default top 10 | 96 | 32.7 | 33.3 | provisional, 5 of 7 |

**Why**

- **BGR moves up to first.** Its Demand Momentum is 85.7 and its Capacity Pressure is 75.9.
- **HVN moves up from fourth to second.** It has the highest Demand Momentum among the established candidates (91.1), and the heavier growth weight outweighs its modest Capacity Pressure (56.2).
- **BOS falls from first to fourth.** Its Demand Momentum is the weakest of its Pillars (50.2), so it loses most when growth is weighted more heavily. Its Capacity Pressure (86.1) and Market Scale (95.3) are unchanged.
- **BTV holds third.** It is balanced across all three Pillars.
- **MVY rises from ninth to seventh** on Demand Momentum of 82.1, despite a low Market Scale (28.4).
- **BID and WST enter the top 10.** They have very high Demand Momentum (96.2 and 96) but weak Capacity Pressure (32.4 and 32.7) and small Market Scale. They are growth-only outliers, and their scores rest partly on imputed data.
- **BDL and MHT drop out of the top 10.** The tool shows only the top 10, so I can't give their new ranks.

**Assumptions & scope**

- This is a screening list of airports worth investigating. It is not proof that an expansion would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- HVN, PSM, BID and WST have Provisional Scores. Delay share and taxi-out were imputed at the median because each has fewer than 1,000 reporting-carrier departures.
- On-Time data covers only the largest US reporting carriers and domestic flights.
- The alternative reading of "twice as much" would be to double growth relative to a fixed total. The tool's normalisation already does this.

**Data Confidence:** Medium.
- 6 of 10 listed airports have full Coverage (7 of 7). HVN, PSM, BID and WST are provisional at 5 of 7.
- Sources and windows:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: FY2024 actual to FY2035 forecast.
  - BTS T-100: Aug 2025–Jul 2026.
  - BTS On-Time: Sep 2025–Aug 2026.
  - Census population: Jul 1, 2025 estimate.

*13 s, $0.074*

---

## G6. How many flights left BOS for Europe last summer?

**Tool calls**

- `query_snapshot` (long arguments)

  ```sql
  SELECT year, month, service_class, SUM(departures_performed) AS deps FROM t100_routes WHERE origin='BOS' AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') AND month IN (6,7,8) AND year >= 2025 GROUP BY ROLLUP (year, month, service_class) ORDER BY year, month, service_class
  ```

- `suggest_followups({"questions": ["Which European cities had the most departures from BOS in summer 2026?", "What is BOS's long-haul share of departures?", "How does BOS summer 2026 Europe traffic compare with BOS's 2025 summer by month?"]})`

**Agent response**

**Answer** (ad hoc query)

2,886 flights left BOS for Europe in June–July 2026. That is all service classes, departures performed. The Snapshot ends in Jul 2026, so August 2026 is missing and this is a partial summer.

| Month | Scheduled passenger (F) | Charter (L) | Other (P) | All classes |
|---|---|---|---|---|
| Jun 2026 | 1,425 | 7 | – | 1,432 |
| Jul 2026 | 1,447 | 7 | – | 1,454 |
| **Jun–Jul 2026** | | | | **2,886** |

For a full summer, the Jun–Aug 2025 total was 4,397 flights, all classes: 1,432 in June, 1,480 in July and 1,485 in August.

**Why**
- Nearly all of these departures are scheduled passenger flights (class F). Charter flights (L) account for 7 a month in 2026.
- June 2026 matches June 2025 at 1,432 all-class departures. July 2026 is 1,454, against 1,480 in July 2025.

**Assumptions & scope**
- "Last summer" is June–August of the most recent year in the Snapshot, which is 2026. Only June and July are available.
- "Flights" means departures performed, from the T-100 segment data, all carriers and all service classes. I did not give a passenger-only (F) total for the two months, because the tool returned only the monthly F figures and I don't add them myself.
- Europe uses the standard ISO-2 country list. Turkey is excluded.
- The query counts BOS as the origin only and covers nonstop segments to European countries.
- The SQL was written by me over the Snapshot views.

**Data Confidence:** Medium. The query is ad hoc and outside the scoring methodology. The source is BTS T-100 Segment (All Carriers), as of Jul 2026, with a 24-month window of Aug 2024–Jul 2026.

*12 s, $0.026*
