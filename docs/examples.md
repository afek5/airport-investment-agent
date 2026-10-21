# Example transcripts: golden questions G1–G6

Recorded from one live run of `make test-live` (real Claude, model `anthropic:claude-sonnet-5-5`, Snapshot built 2026-10-21T18:32:22Z). Every number in each answer passed the number-grounding check: it appears in a tool result of the same run. G5 is a follow-up in the G1 conversation. Regenerate with `WRITE_EXAMPLES=1 make test-live`.

Total model cost of the six answers: $0.24.

## G1. Which airports in New England are strong candidates for terminal expansion?

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"], "top_n": 10})`
- `suggest_followups({"questions": ["What if growth matters twice as much for New England airports?", "Which unmet demand does BOS show, and why?", "Compare congestion at BOS, BDL and PVD"]})`

**Agent response**

**Answer**

New England here means CT, ME, MA, NH, RI and VT. The table shows the top 10 of 16 ranked Primary Airports, under the default Pillar Weights.

| Rank | Airport | Hub Size | Investment Opportunity Score | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BOS (Boston Logan) | L | 73.1 | 50.2 | 86.1 | 95.3 | 7/7 |
| 2 | BGR (Bangor) | N | 72.4 | 85.7 | 75.9 | 53.0 | 7/7 |
| 3 | BTV (Burlington) | S | 71.9 | 69.4 | 82.8 | 60.4 | 7/7 |
| 4 | HVN (Tweed/New Haven) | S | 69.9 | 91.1 | 56.2 | 68.1 | 5/7, provisional |
| 5 | PWM (Portland, ME) | S | 64.8 | 64.3 | 60.8 | 72.6 | 7/7 |
| 6 | PVD (Providence) | S | 62.8 | 65.0 | 51.8 | 81.6 | 7/7 |
| 7 | PSM (Portsmouth, NH) | N | 60.1 | 57.9 | 64.6 | 56.4 | 5/7, provisional |
| 8 | BDL (Bradley) | M | 57.0 | 41.2 | 59.8 | 83.5 | 7/7 |
| 9 | MVY (Martha's Vineyard) | N | 54.7 | 82.1 | 57.7 | 28.4 | 7/7 |
| 10 | MHT (Manchester) | S | 52.2 | 61.5 | 35.7 | 76.3 | 7/7 |

**Why**

The score is a weighted geometric mean, so airports that are decent on all three Pillars beat airports that are strong on only one.
- **BOS:** It has the highest Market Scale (95.3) and Capacity Pressure (86.1) in the group. Its Demand Momentum is only mid-range (50.2), and that holds it just ahead of BGR.
- **BGR:** It has strong Demand Momentum (85.7) and good Capacity Pressure (75.9). Its Market Scale is modest (53.0), which is expected for a nonhub airport.
- **BTV:** It is balanced, with Capacity Pressure of 82.8, Demand Momentum of 69.4 and Market Scale of 60.4.
- **HVN:** It has the highest Demand Momentum (91.1) of the ten. Its Capacity Pressure (56.2) is partly imputed, so treat its rank with caution.

**Assumptions & scope**
- I mapped New England to CT, ME, MA, NH, RI and VT, and ranked on the default Pillar Weights (Demand Momentum 0.35, Capacity Pressure 0.40, Market Scale 0.25). I can re-run with different weights.
- HVN and PSM are Provisional Scores. Delay share and taxi-out were imputed at the median because they have fewer than 1,000 reporting-carrier departures.
- On-Time data covers only the largest reporting US carriers and domestic flights. Delay and taxi-out say nothing about international operations.
- Screening caveat: this is a candidate list, not proof that a terminal project would be profitable. The tools have no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- Six ranked airports are not shown (top 10 of 16).

**Data Confidence:** Medium.
- 8 of the 10 listed airports have full Coverage (7/7). HVN and PSM are provisional at 5/7.
- Some airports have no On-Time coverage because they have fewer than 1,000 reporting-carrier departures.
- Windows:
  - T-100: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF: FY2024 actual to FY2035 forecast.
  - Census population: Jul 1, 2025 estimate.

*12 s, $0.034*

---

## G2. Compare LA and Santa Ana airport congestion levels.

**Tool calls**

- `resolve_airports({"query": "LA"})`
- `resolve_airports({"query": "Santa Ana"})`
- `compare_airports({"iatas": ["LAX", "SNA"], "lens": "congestion"})`
- `live_delays({"iatas": ["LAX", "SNA"]})`
- `suggest_followups({"questions": ["How do LAX and SNA compare on Investment Opportunity Score?", "What is the Unmet Demand picture at SNA?", "How do LAX, BUR, LGB, ONT and SNA compare on congestion?"]})`

**Agent response**

**Answer**

LAX is more congested than SNA overall. Its congestion_index is 57.5, against 50.1 for SNA. The gap comes from taxi-out time, runway use and load factor. The two airports have the same share of delayed departures. Neither has an active delay now.

| Metric | LAX (percentile) | SNA (percentile) |
|---|---|---|
| Departures delayed ≥15 min | 20.6% (58.5) | 20.6% (56.8) |
| Average taxi-out | 18.2 min (68.5) | 16.1 min (38.2) |
| Cancelled departures | 1.0% (17.8) | 1.1% (20.3) |
| NAS delay per departure | 3.0 min (45.6) | 3.5 min (55.2) |
| Departures per month (all T-100 classes) | 22,265.6 (99.0) | 4,283.0 (88.5) |
| Departures per runway per day | 182.9 (98.5) | 70.4 (90.7) |
| Load factor (class F) | 82.3% (90.5) | 79.8% (74.4) |
| Runways | 4 | 2 |
| **congestion_index** | **57.5** | **50.1** |

**Why**
- **LAX:** Taxi-out is the main difference, at 18.2 min (68.5th percentile) against 16.1 min (38.2nd) at SNA. LAX also handles 182.9 departures per runway per day (98.5th percentile) against 70.4 at SNA (90.7th). Its load factor is 82.3%, against 79.8% at SNA.
- **SNA:** It does better on taxi-out and load factor. It is slightly worse on NAS delay per departure, at 3.5 min against 3.0 min at LAX. Its cancellation rate is 1.1% against 1.0%. SNA is still in the top decile for runway intensity, with only 2 runways.
- **Live Signal:** Neither airport has an active ground stop or delay program. LAX has a closure notice that applies only to non-scheduled transient general aviation, so airline operations are not affected.

**Assumptions & scope**
- "LA" is taken to be LAX. The alternates were BUR, LGB and ONT, and SNA is the other airport you named.
- The congestion_index is the mean national percentile of delay share, taxi-out and NAS delay per departure. It is a congestion lens, not the Investment Opportunity Score.
- On-Time data covers only reporting carriers and domestic flights, so delay and taxi-out say nothing about international operations.
- Percentiles are national, among Primary Airports that have each metric.
- Live status is a point-in-time Live Signal and does not affect any score.

**Data Confidence:** High. Every compared metric is measured for both airports.
- T-100 (departures, load factor): 12 months, Aug 2025–Jul 2026.
- On-Time (delay, taxi-out): 12 months, Sep 2025–Aug 2026.
- FAA NAS Status: as of Wed Oct 21 19:26:57 2026 GMT.

*13 s, $0.039*

---

## G3. What is the percentage of long haul flights out of Anchorage airport?

**Tool calls**

- `route_mix({"iata": "ANC"})`
- `suggest_followups({"questions": ["How does Anchorage's long-haul share change with a 4,000-mile threshold?", "Is Anchorage a strong candidate for terminal investment?", "What is the latest monthly traffic at Anchorage?"]})`

**Agent response**

**Answer**

For Ted Stevens Anchorage (ANC), **2.7%** of scheduled passenger departures are long-haul. A Long-haul Flight is a segment of 3,000 statute miles or more. The tool returned three figures, and they differ a lot:

| Measure | Long-haul | Total | Share |
|---|---|---|---|
| (a) **Headline:** scheduled passenger (class F) departures | 1,005 | 37,243 | **2.7%** |
| (b) Passenger-weighted (passengers on long-haul segments / all class F passengers) | 166,414 | 2,699,637 | 6.2% |
| (c) Cargo-inclusive (all service classes) | 25,743 | 87,249 | 29.5% |

**Why**

ANC is a cargo hub, which is why the cargo-inclusive figure is so much higher.
- Non-passenger departures (classes G, L and P) are 57.3% of all departures.
- All-cargo flights (classes G + P) account for 24,643 of the 25,743 long-haul departures. That is 95.7% of all long-haul departures (`all_cargo_share_of_long_haul_pct`).
- Per-class long-haul shares of each class's own departures:
  - Scheduled cargo (G): 48.0%.
  - Non-scheduled cargo/other (P): 60.5%.
  - Scheduled passenger (F): 2.7%.
- Typically these are freighters stopping at Anchorage between Asia and North America.
- Passenger long-haul flying is mostly US domestic routes just over 3,000 miles, such as DFW (388 departures), ATL (156), IAH (128), IAD (110) and EWR (101). The only international long-haul passenger destinations listed are FRA (30 departures), HND (6) and ICN (2).
- Long-haul passengers are a larger share of passengers (6.2%) than of flights (2.7%).

**Assumptions & scope**
- Window: 12 months, Aug 2025–Jul 2026.
- Counts are departures performed from ANC.
- T-100 reports flight segments, so a multi-stop flight counts each leg separately.
- Zero-departure rows are dropped, and carriers and aircraft types are aggregated.
- Class L charters can carry passengers. "Non-passenger" means G, L and P, and "all-cargo" means G and P.
- The top-destinations list covers class F only.

**Data Confidence:** High. T-100 is a census of all carriers' segments. Source: BTS T-100 Segment (All Carriers), as of Jul 2026, 12-month window Aug 2025–Jul 2026.

*9 s, $0.024*

---

## G4. What is the unmet flight demand in SFO airport and why?

**Tool calls**

- `unmet_demand({"iata": "SFO"})`
- `od_demand({"iata": "SFO"})`
- `suggest_followups({"questions": ["How does SFO compare with LAX and SEA on congestion?", "Are there any live delays or ground stops at SFO right now?", "Which large hubs rank highest for terminal expansion?"]})`

**Agent response**

**Answer**

The data can't measure SFO's unmet demand directly, because no public source records turned-away passengers. The observed Constraint Evidence shows SFO as a constrained airport, and the FAA forecast has it growing well beyond today's level.

| Constraint Evidence | SFO | National median |
|---|---|---|
| Departures delayed ≥15 min | 25.3% | 20.0% |
| Average taxi-out | 23.0 min | 16.8 min |
| Load Factor, scheduled passenger flights (class F) | 82.1% | 75.8% |
| Route-months with Load Factor above 0.85 | 35.2% | 18.6% |
| NAS delay per departure | 3.9 min | 3.3 min |

- **Forecast Gap (FAA TAF, FY2024 → FY2030):** enplanements go from 24,765,642 to 30,516,426, a rise of 5,750,784 (23.2%). Air-carrier operations go from 350,805 to 435,218, a rise of 24.1%.

**Why**

The drivers are listed in order of strength:
1. **Taxi-out:** 23.0 min against a median of 16.8 min, at the 96.3rd national percentile.
2. **Load Factor:** 82.1%, at the 89.4th percentile.
3. **Delays:** 25.3% of departures are delayed 15+ minutes, at the 88.4th percentile.
4. **Full route-months:** 35.2% of route-months are above 0.85 load factor, at the 83.4th percentile.
5. **Weather capacity:** the arrival rate drops 33.3% in bad weather, from 54/hr (VFR) to 36/hr (IFR). This is from the FAA 2019 capacity profile.
6. **NAS delay:** 3.9 min per departure against a median of 3.3 min, at the 64.7th percentile.

Supply is not clearly falling behind demand. Passenger growth is 0.6% against seat growth of 0.7%, a gap of -0.1 pp. The national median gap is -0.9 pp.

The busiest O&D markets (DOT Consumer Airfare Report, 2026 Q1) show where demand is concentrated:

| Market | Passengers/day | Average fare | Largest carrier (share) |
|---|---|---|---|
| LAX | 4,717.5 | $172.46 | UA (33.5%) |
| JFK | 3,721.4 | $494.88 | DL (43.6%) |
| EWR | 2,941.4 | $571.70 | UA (86.1%) |
| LAS | 2,743.4 | $198.56 | UA (36.7%) |
| SAN | 2,472.4 | $185.80 | UA (38.8%) |

The transcontinental markets (JFK, EWR, BOS) have the highest fares. EWR is dominated by United, while low-fare carriers hold 11.4%–16.1% of the JFK and EWR markets. This is consistent with tight capacity, but it does not prove it.

**Spill Scenario** (a scenario under assumed spill rates, not calibrated and not observed): the assumed rates give a range of 396,415 to 839,701 passengers. The routes that contribute most are EWR, JFK, ORD, DFW and HNL. This is a sensitivity, not a measurement of demand SFO failed to serve.

**Assumptions & scope**
- Delay and taxi-out come from reporting carriers' domestic flights only. They say nothing about international operations.
- The IFR/VFR capacity figures are from 2019. The Airport Capacity Profile cross-check gives 100–110 ops/hr in visual conditions and 70–72 in instrument conditions.
- The O&D data covers only the largest domestic markets, from one quarter of a 10% ticket sample.
- Current NAS status is a Live Signal and is not in this evidence. I did not check it.
- **What the data can't tell us:**
  - Actual denied or turned-away passengers.
  - Demand recaptured by nearby airports such as OAK and SJC.
  - Whether the binding constraint is the terminal, the gates or the runway/airspace.
  - Airline network choices versus infrastructure limits.
  - Project cost and revenue.

**Data Confidence:** Medium.
- Unmet Demand is argued from observed indicators and an official forecast. Turned-away passengers are not observed in any public data.
- The Spill Scenario rests on assumed, uncalibrated spill rates.
- The O&D data comes from a 10% ticket sample and covers one quarter.
- **Windows:**
  - T-100: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA TAF 2025: FY2024 actual to FY2030 forecast.
  - DOT Consumer Airfare Report: 2026 Q1.

*15 s, $0.046*

---

## G5. What if growth matters twice as much?

*(Follow-up in the G1 conversation.)*

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"], "top_n": 10, "weights": {"momentum": 0.7, "pressure": 0.4, "scale": 0.25}})`
- `suggest_followups({"questions": ["What if congestion (Capacity Pressure) matters twice as much instead?", "Show the full scorecard for BGR", "Compare demand momentum at BGR, HVN and BTV"]})`

**Agent response**

**Answer**

With Demand Momentum doubled, BGR moves to #1 and BOS drops from #1 to #4. HVN and MVY also move up.

| New rank | Airport | Score (default → growth ×2) | Old rank | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BGR | 72.4 → 75.6 | 2 | 85.7 | 75.9 | 53.0 | 7/7 |
| 2 | HVN | 69.9 → 74.8 | 4 | 91.1 | 56.2 | 68.1 | 5/7, provisional |
| 3 | BTV | 71.9 → 71.3 | 3 | 69.4 | 82.8 | 60.4 | 7/7 |
| 4 | BOS | 73.1 → 66.4 | 1 | 50.2 | 86.1 | 95.3 | 7/7 |
| 5 | PWM | 64.8 → 64.7 | 5 | 64.3 | 60.8 | 72.6 | 7/7 |
| 6 | PVD | 62.8 → 63.4 | 6 | 65.0 | 51.8 | 81.6 | 7/7 |
| 7 | MVY | 54.7 → 60.8 | 9 | 82.1 | 57.7 | 28.4 | 7/7 |
| 8 | PSM | 60.1 → 59.5 | 7 | 57.9 | 64.6 | 56.4 | 5/7, provisional |
| 9 | BID (Block Island) | not in the earlier top 10 → 57.4 | – | 96.2 | 32.4 | 33.7 | 5/7, provisional |
| 10 | WST (Westerly) | not in the earlier top 10 → 57.4 | – | 96.0 | 32.7 | 33.3 | 5/7, provisional |

**Why**
- **Winners:** The airports with the strongest Demand Momentum gain most. HVN (91.1), BGR (85.7) and MVY (82.1) all rise.
- **BOS:** Its Demand Momentum is only 50.2. Its Market Scale (95.3) and Capacity Pressure (86.1) now count for less, so it falls to #4.
- **BDL and MHT:** Both drop out of the top 10. Their Demand Momentum is below 62 and their other Pillars are not strong enough to offset it.
- **BID and WST:** These small RI airports enter the top 10 on Demand Momentum alone (96.2 and 96.0). Their Capacity Pressure and Market Scale are weak, and both are provisional. I'd treat them as weak candidates despite the rank.
- **BTV and PWM:** Their scores barely change because their Pillars are balanced.

**Assumptions & scope**
- "Twice as much" means Demand Momentum is doubled to 0.70 against Capacity Pressure at 0.40 and Market Scale at 0.25. The tool normalised these to 0.52, 0.30 and 0.19. The scope is the same six states as before.
- HVN, PSM, BID and WST are Provisional Scores. Delay share and taxi-out were imputed at the median.
- The tool's top 10 of 16 ranked airports are shown.
- Screening caveat: this is a candidate list, not proof of profitability. The tools have no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- On-Time data covers only reporting carriers and domestic flights.

**Data Confidence:** Medium.
- 6 of the 10 listed airports have full Coverage (7/7). HVN, PSM, BID and WST are provisional at 5/7.
- Some airports have no On-Time coverage because they have fewer than 1,000 reporting-carrier departures.
- Windows:
  - T-100: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF: FY2024 actual to FY2035 forecast.
  - Census population: Jul 1, 2025 estimate.

*11 s, $0.064*

---

## G6. How many flights left BOS for Europe last summer?

**Tool calls**

- `query_snapshot({"sql": "SELECT year, month, COUNT(*) AS n_rows FROM t100_routes GROUP BY year, month ORDER BY year, month"})`

  ```sql
  SELECT year, month, COUNT(*) AS n_rows FROM t100_routes GROUP BY year, month ORDER BY year, month
  ```

- `query_snapshot` (long arguments)

  ```sql
  SELECT month, service_class, SUM(departures_performed) AS departures FROM t100_routes WHERE origin='BOS' AND year=2026 AND month IN (6,7) AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') GROUP BY ROLLUP (month, service_class) ORDER BY month, service_class
  ```

- `suggest_followups({"questions": ["Which European cities had the most departures from BOS last summer?", "What share of BOS departures are long-haul flights?", "How does BOS rank for terminal expansion among large hubs?"]})`

**Agent response**

**Answer**

This is an ad hoc result. The Snapshot shows 2,886 departures from BOS to Europe in June–July 2026, counting all service classes. August 2026 isn't in the Snapshot yet.

| Month (2026) | Scheduled passenger (class F) | Charter (class L) | All classes |
|---|---|---|---|
| June | 1,425 | 7 | 1,432 |
| July | 1,447 | 7 | 1,454 |
| **June–July total** | not returned as a single figure | not returned as a single figure | **2,886** |

**Why**

- Almost all of these departures are scheduled passenger flights. The monthly class F counts are 1,425 and 1,447.
- Charter flights (class L) are 7 per month.
- The tool returned no June–July total for class F alone, so I haven't added the two months myself.

**Assumptions & scope**

- "Last summer" means June–August of the most recent year in the Snapshot, which is 2026. The Snapshot ends in July 2026, so August is missing and the count covers June and July only.
- "Flights" means T-100 `departures_performed`, which counts segments that left BOS.
- Europe uses the standard ISO-2 country list from my instructions. Turkey (TR) is excluded. Russia is not in that list either.
- Counts cover all carriers combined. Segments with zero departures are dropped from the data.
- Only departures from BOS are counted. Flights to BOS aren't included.

**Data Confidence**

- Medium. The query is ad hoc and sits outside the scoring methodology, so check the SQL and the months it covers.
- Source: BTS T-100 Segment (All Carriers). As-of date is Jul 2026, and the Snapshot window is Aug 2024–Jul 2026.

*12 s, $0.031*
