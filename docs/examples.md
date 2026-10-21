# Example transcripts: golden questions G1–G6

Recorded from one live run of `make test-live` (real Claude, model `anthropic:claude-sonnet-5-5`, Snapshot built 2026-10-21T18:32:22Z). Every number in each answer passed the number-grounding check: it appears in a tool result of the same run. G5 is a follow-up in the G1 conversation. Regenerate with `WRITE_EXAMPLES=1 make test-live`.

Total model cost of the six answers: $0.25.

## G1. Which airports in New England are strong candidates for terminal expansion?

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"]})`
- `suggest_followups({"questions": ["What if growth matters twice as much for New England airports?", "Show the Unmet Demand evidence for Bangor (BGR)", "Compare congestion at BOS, BTV and PVD"]})`

**Agent response**

**Answer**

The top 10 of 16 ranked New England Primary Airports, by Investment Opportunity Score at default Pillar Weights:

| Rank | Airport | Hub Size | Score | Momentum | Pressure | Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BOS (Boston Logan, MA) | L | 73.1 | 50.2 | 86.1 | 95.3 | 7 of 7 |
| 2 | BGR (Bangor, ME) | N | 72.4 | 85.7 | 75.9 | 53 | 7 of 7 |
| 3 | BTV (Burlington, VT) | S | 71.9 | 69.4 | 82.8 | 60.4 | 7 of 7 |
| 4 | HVN (Tweed New Haven, CT) | S | 69.9 | 91.1 | 56.2 | 68.1 | 5 of 7, provisional |
| 5 | PWM (Portland, ME) | S | 64.8 | 64.3 | 60.8 | 72.6 | 7 of 7 |
| 6 | PVD (Providence, RI) | S | 62.8 | 65 | 51.8 | 81.6 | 7 of 7 |
| 7 | PSM (Portsmouth Pease, NH) | N | 60.1 | 57.9 | 64.6 | 56.4 | 5 of 7, provisional |
| 8 | BDL (Bradley, CT) | M | 57 | 41.2 | 59.8 | 83.5 | 7 of 7 |
| 9 | MVY (Martha's Vineyard, MA) | N | 54.7 | 82.1 | 57.7 | 28.4 | 7 of 7 |
| 10 | MHT (Manchester, NH) | S | 52.2 | 61.5 | 35.7 | 76.3 | 7 of 7 |

BOS, BGR and BTV are the strongest candidates. The scores of the top three are close.

**Why**
- **BOS:** It has the highest Market Scale (95.3) and a high Capacity Pressure (86.1). Its Demand Momentum is only middling (50.2), so it ranks first on size and strain, not growth.
- **BGR:** It has strong Demand Momentum (85.7) and solid Capacity Pressure (75.9). Its Market Scale is modest (53), which is typical for a nonhub.
- **BTV:** It is the most balanced of the three. Capacity Pressure is 82.8, Demand Momentum is 69.4 and Market Scale is 60.4.
- **HVN:** It has the highest Demand Momentum in the group (91.1). Its Capacity Pressure is only 56.2, and that figure uses imputed delay and taxi-out values.
- **BDL, PVD and MHT:** They are large markets (Scale 83.5, 81.6 and 76.3). Their rankings are held back by weaker Momentum (BDL 41.2) or weaker Pressure (MHT 35.7, PVD 51.8).

**Assumptions & scope**
- I took New England to be CT, ME, MA, NH, RI and VT. The ranking uses default Pillar Weights of Demand Momentum 0.35, Capacity Pressure 0.40 and Market Scale 0.25. I showed 10 of the 16 ranked airports.
- HVN and PSM are Provisional Scores. They have fewer than 1,000 reporting-carrier departures, so delay share and taxi-out were imputed at the median. That pulls their Capacity Pressure toward the middle.
- On-Time data covers only reporting carriers on domestic flights. Delay and taxi-out say nothing about international operations.
- This is a screening list of candidates, not proof that a terminal expansion would be profitable. The data has no project cost, terminal or gate utilisation, commercial revenue or feasibility figures.

**Data Confidence:** Medium.
- 8 of the 10 listed airports have full Coverage (7 of 7).
- HVN and PSM are provisional at 5 of 7, with delay share and taxi-out imputed.
- Some airports have no On-Time coverage because they have fewer than 1,000 reporting-carrier departures.
- Windows:
  - T-100 load factor: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA enplanements: CY2024–CY2025.
  - TAF: FY2024 actual to FY2035 forecast.
  - Census population: Jul 1, 2025 estimate.

*15 s, $0.035*

---

## G2. Compare LA and Santa Ana airport congestion levels.

**Tool calls**

- `resolve_airports({"query": "LA"})`
- `resolve_airports({"query": "Santa Ana"})`
- `compare_airports({"iatas": ["LAX", "SNA"], "lens": "congestion"})`
- `live_delays({"iatas": ["LAX", "SNA"]})`
- `suggest_followups({"questions": ["Rank Southern California airports for terminal expansion", "How much unmet demand does SNA show and why?", "Compare LAX and SNA on the Investment Opportunity Score"]})`

**Agent response**

**Answer**

LAX is the more congested airport on the congestion lens. Its congestion_index is 57.5, against 50.1 for SNA. Most of the gap comes from taxi-out time, runway intensity and load factor. Delay share is identical. Neither airport has an active delay right now.

| Metric (national percentile) | LAX | SNA |
|---|---|---|
| Congestion index (a lens, not the Investment Opportunity Score) | 57.5 | 50.1 |
| Departures delayed ≥15 min | 20.6% (58.5) | 20.6% (56.8) |
| Average taxi-out | 18.2 min (68.5) | 16.1 min (38.2) |
| NAS delay per departure | 3 min (45.6) | 3.5 min (55.2) |
| Cancelled departures | 1% (17.8) | 1.1% (20.3) |
| Departures per month (all T-100 classes) | 22,265.6 (99) | 4283 (88.5) |
| Departures per runway per day | 182.9 (98.5) | 70.4 (90.7) |
| Load factor, class F | 82.3% (90.5) | 79.8% (74.4) |
| Runways | 4 | 2 |

**Why**
- **Delay share:** both airports are at 20.6%, so delays alone don't separate them.
- **Taxi-out:** LAX averages 18.2 min (68.5th percentile) and SNA 16.1 min (38.2nd percentile). This is the biggest gap in the delay-type metrics.
- **NAS delay:** SNA is slightly higher, at 3.5 min per departure against 3 for LAX.
- **Runway load:** LAX handles 182.9 departures per runway per day, against 70.4 at SNA. SNA is still in the 90.7th percentile nationally, so it is busy for its size.
- **Load factor:** LAX is at 82.3% and SNA at 79.8%.
- **Cancellations:** both are low, at 1% and 1.1%.
- **Live status:** the FAA feed shows no active delay at either airport. LAX has only a closure notice for non-scheduled transient general aviation, which does not affect airline operations.

**Assumptions & scope**
- "LA" is taken as LAX (Los Angeles International). The alternates were BUR, LGB and ONT. "Santa Ana" is SNA (John Wayne/Orange County).
- National percentiles are measured among FAA Primary Airports that have each metric.
- The congestion_index is the mean percentile of delay share, taxi-out and NAS delay. It is a lens, not the Investment Opportunity Score.
- On-Time data covers only reporting carriers and domestic flights. Delay and taxi-out therefore say nothing about international operations.
- Departures per month and per runway use all T-100 service classes and the OurAirports runway count.

**Data Confidence**
High, because every compared metric is measured for both airports.
- **T-100:** 12 months, Aug 2025–Jul 2026 (as of Jul 2026).
- **On-Time:** 12 months, Sep 2025–Aug 2026 (as of Aug 2026).
- **Live status:** FAA NAS Status, as of Wed Oct 21 20:00:18 2026 GMT.

*14 s, $0.040*

---

## G3. What is the percentage of long haul flights out of Anchorage airport?

**Tool calls**

- `route_mix({"iata": "ANC"})`
- `suggest_followups({"questions": ["How does Anchorage's long-haul share compare with Seattle or Honolulu?", "Which airports have the highest share of long-haul passenger flights?", "What is Anchorage's Investment Opportunity Score?"]})`

**Agent response**

**Answer**

Long-haul Flight = a segment of 3,000 statute miles or more. At Anchorage (ANC), the share depends on which flights you count:

| Measure | Long-haul | Total | Share |
|---|---|---|---|
| (a) **Headline:** scheduled passenger (class F) departures | 1005 | 37,243 | **2.7%** |
| (b) Passenger-weighted (passengers on long-haul segments / all class F passengers) | 166,414 | 2,699,637 | 6.2% |
| (c) Cargo-inclusive (all service classes, a labelled variant) | 25,743 | 87,249 | 29.5% |

**Why**

ANC is a cargo hub, and that is why (c) is so much higher than (a).
- Non-passenger departures (classes G, L and P) are 57.3% of all departures.
- All-cargo flights (classes G + P) make 24,643 of the 25,743 long-haul departures, which is 95.7% of all long-haul departures. This is consistent with freighters stopping at Anchorage between Asia and North America.
- By class, 48% of scheduled cargo (G) departures are long-haul, with 16,234 long-haul departures. Non-scheduled cargo (P) is 60.5% long-haul, with 8409 long-haul departures. Scheduled passenger (F) is 2.7% long-haul, with 1005 long-haul departures, which is 3.9% of all long-haul departures.
- The long-haul passenger flights are mostly domestic routes to US hubs:

| Destination | Departures |
|---|---|
| DFW | 388 |
| ATL | 156 |
| IAH | 128 |
| IAD | 110 |
| EWR | 101 |
| JFK | 71 |

- International long-haul passenger flights are few: FRA has 30 departures, HND 6 and ICN 2.

**Assumptions & scope**
- The headline counts class F departures performed from ANC.
- T-100 reports flight segments, so a multi-stop flight counts each leg separately.
- Zero-departure rows are dropped, and carriers and aircraft types are aggregated.
- Non-passenger means classes G, L and P. All-cargo means classes G and P, because L charters can carry passengers.
- Alternative: use the cargo-inclusive 29.5% if you mean all aircraft movements rather than passenger service.

**Data Confidence**

High. T-100 is a census of all carriers' segments. Source: BTS T-100 Segment (All Carriers), as of Jul 2026, 12-month window Aug 2025–Jul 2026.

*9 s, $0.024*

---

## G4. What is the unmet flight demand in SFO airport and why?

**Tool calls**

- `unmet_demand({"iata": "SFO"})`
- `od_demand({"iata": "SFO"})`
- `suggest_followups({"questions": ["How does SFO's Investment Opportunity Score compare with LAX, SEA and BOS?", "Are there active delays or ground stops at SFO right now?", "What is SFO's long-haul share of departures?"]})`

**Agent response**

**Answer**

The data can't measure SFO's unmet demand directly, because no public data records turned-away passengers. It does show an airport under strain, and a forecast that adds more traffic.

- **Constraint Evidence (observed):**

| Indicator | SFO | National median (Primary Airports) |
|---|---|---|
| Average taxi-out | 23 min | 16.8 min |
| Load Factor, class F | 82.1% | 75.8% |
| Departures delayed ≥15 min | 25.3% | 20% |
| Route-months with Load Factor above 0.85 | 35.2% | 18.6% |

- **Forecast Gap (FAA TAF, FY2024 → FY2030):**
  - Enplanements rise from 24,765,642 to 30,516,426, which is 23.2%.
  - Air-carrier operations rise from 350,805 to 435,218, which is 24.1%.

**Why**

The tool ranks these drivers by strength, which is SFO's national percentile on each indicator:
1. **Taxi-out** is at the 96.3rd percentile. Aircraft spend a long time on the ground before takeoff.
2. **Load Factor** is at the 89.4th percentile, so flights are unusually full.
3. **Delay share** is at the 88.4th percentile.
4. **Full route-months** are at the 83.4th percentile.
5. **Weather capacity:** The FAA Capacity Profile (2019) gives an arrival rate of 54/hr in clear weather (VFR) and 36/hr in bad weather (IFR). That is a 33.3% drop, so SFO has little slack when the weather turns.
6. **NAS delay** (airspace and airport) is 3.9 min per departure against a median of 3.3 min, at the 64.7th percentile. This is a weaker driver.

Growth is not the pressure source. Passenger growth over the last 12 months against the prior 12 was 0.6%, and seat growth was 0.7%. Passenger growth minus seat growth was -0.1 pp, against a national median of -0.9 pp. The strain comes from a fixed-capacity airport running full, not from a surge in traffic.

**Market side (DOT Consumer Airfare Report, 2026 Q1, Live Signal)**

| Market | Passengers/day | Avg fare | Largest carrier (share) |
|---|---|---|---|
| LAX | 4,717.5 | $172.46 | UA (33.5%) |
| JFK | 3,721.4 | $494.88 | DL (43.6%) |
| EWR | 2,941.4 | $571.70 | UA (86.1%) |
| LAS | 2,743.4 | $198.56 | UA (36.7%) |
| ORD | 2,247.6 | $338.47 | UA (69.5%) |

- Transcontinental fares are high. The EWR market is dominated by UA, and ORD and DEN are also UA-led, so competition is thin on those routes.
- Low-fare carriers hold only 11.4–16.1% of the EWR, JFK and DEN markets.

**Spill Scenario** (a scenario under assumed spill rates, not calibrated and not observed)

- Under the assumed rates, the tool gives a range of 396,415 to 839,701 passengers.
- The routes with the most full months are EWR (12 months over the threshold), JFK (10), ORD (10), DFW (10) and HNL (9).
- Full aircraft alone do not prove that passengers were turned away.

**Assumptions & scope**

- Benchmarks are national medians of Primary Airports.
- On-Time data covers only large reporting carriers and domestic flights. Delay and taxi-out say nothing about international operations.
- The airfare report covers only large domestic contiguous-US markets, so international markets are excluded. It is one quarter of data from the DB1B 10% ticket sample.
- The runway-capacity figure is from 2019, so it is dated.
- **What the data can't tell us:**
  - Actual denied or turned-away passengers.
  - Demand recaptured at nearby airports such as OAK or SJC.
  - Whether the binding constraint is the terminal, the gates or the runway and airspace.
  - Airline network choices versus infrastructure limits.
  - Project cost and revenue.
- This is a screening signal, not proof that a project would be profitable.

**Data Confidence: Medium**
- Unmet Demand is argued from observed indicators and an official forecast. Turned-away passengers are not observed in any public data.
- The Spill Scenario rests on assumed, uncalibrated spill rates.
- **Windows:**
  - T-100: 12 months, Aug 2025–Jul 2026 (as of Jul 2026).
  - On-Time: 12 months, Sep 2025–Aug 2026 (as of Aug 2026).
  - FAA TAF 2025: FY2024 actual to FY2030 forecast.
  - DOT airfare report: 2026 Q1, one quarter.

*18 s, $0.046*

---

## G5. What if growth matters twice as much?

*(Follow-up in the G1 conversation.)*

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"], "weights": {"momentum": 0.7, "pressure": 0.4, "scale": 0.25}})`
- `suggest_followups({"questions": ["What if Capacity Pressure matters twice as much for New England?", "Show the Unmet Demand evidence for Bangor (BGR)", "Show the full scorecard for HVN"]})`

**Agent response**

**Answer**

With Demand Momentum doubled, BGR takes first place and BOS drops from first to fourth. Here are the top 10 of 16 ranked airports, with the default-weight rank alongside.

| New rank | Airport | Score | Momentum | Pressure | Scale | Default rank | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BGR | 75.6 | 85.7 | 75.9 | 53 | 2 | 7 of 7 |
| 2 | HVN | 74.8 | 91.1 | 56.2 | 68.1 | 4 | 5 of 7, provisional |
| 3 | BTV | 71.3 | 69.4 | 82.8 | 60.4 | 3 | 7 of 7 |
| 4 | BOS | 66.4 | 50.2 | 86.1 | 95.3 | 1 | 7 of 7 |
| 5 | PWM | 64.7 | 64.3 | 60.8 | 72.6 | 5 | 7 of 7 |
| 6 | PVD | 63.4 | 65 | 51.8 | 81.6 | 6 | 7 of 7 |
| 7 | MVY | 60.8 | 82.1 | 57.7 | 28.4 | 9 | 7 of 7 |
| 8 | PSM | 59.5 | 57.9 | 64.6 | 56.4 | 7 | 5 of 7, provisional |
| 9 | BID (Block Island, RI) | 57.4 | 96.2 | 32.4 | 33.7 | not in top 10 | 5 of 7, provisional |
| 10 | WST (Westerly, RI) | 57.4 | 96 | 32.7 | 33.3 | not in top 10 | 5 of 7, provisional |

**Why**
- **Winners:**
  - HVN (Demand Momentum 91.1) moves up two places, to second.
  - MVY (82.1) moves up two places, to seventh.
  - BID and WST enter the top 10 on Momentum of 96.2 and 96, but their Capacity Pressure is low (32.4 and 32.7).
- **Losers:** BOS has middling Momentum (50.2), so it falls to fourth despite the highest Scale (95.3) and Pressure of 86.1. BDL and MHT fall out of the top 10 (neither appears in the new table).
- **Stable:** BTV, PWM and PVD keep their positions, because their Pillars are fairly balanced.
- BGR and BTV have the best mix of strong Momentum and Pressure under either weighting.

**Assumptions & scope**
- **Pillar Weights:** "Twice as much" means Demand Momentum is doubled to 0.70, with Capacity Pressure at 0.40 and Market Scale at 0.25. The tool normalised these to 0.52, 0.30 and 0.19. Pillar scores themselves do not change, only the weighting.
- **Provisional Scores:** HVN, PSM, BID and WST have delay share and taxi-out imputed at the median, because they have fewer than 1,000 reporting-carrier departures. That pulls their Capacity Pressure toward the middle.
- **Reading BID and WST:** They are tiny nonhub airports. Their Momentum is high, but their Pressure and Scale are low, and their Pressure is partly imputed.
- On-Time data covers only reporting carriers on domestic flights.
- This is a screening list, not proof of profitability. The data has no project cost, terminal or gate utilisation, commercial revenue or feasibility figures.

**Data Confidence:** Medium.
- 6 of the 10 listed airports have full Coverage (7 of 7).
- HVN, PSM, BID and WST are provisional at 5 of 7, with delay share and taxi-out imputed.
- Some airports have no On-Time coverage because they have fewer than 1,000 reporting-carrier departures.
- Windows:
  - T-100 load factor: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA enplanements: CY2024–CY2025.
  - TAF: FY2024 actual to FY2035 forecast.
  - Census population: Jul 1, 2025 estimate.

*15 s, $0.064*

---

## G6. How many flights left BOS for Europe last summer?

**Tool calls**

- `query_snapshot` (long arguments)

  ```sql
  SELECT year, month, SUM(departures_performed) AS departures, SUM(CASE WHEN service_class='F' THEN departures_performed ELSE 0 END) AS passenger_f_departures FROM t100_routes WHERE origin='BOS' AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') GROUP BY year, month ORDER BY year, month
  ```

- `query_snapshot` (long arguments)

  ```sql
  SELECT month, SUM(departures_performed) AS departures, SUM(CASE WHEN service_class='F' THEN departures_performed ELSE 0 END) AS passenger_f_departures FROM t100_routes WHERE origin='BOS' AND year=2026 AND month IN (6,7) AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') GROUP BY ROLLUP (month) ORDER BY month
  ```

- `suggest_followups({"questions": ["Which European cities had the most BOS departures in June–July 2026?", "What is BOS's long-haul share of departures?", "How does BOS rank for terminal expansion among large hubs?"]})`

**Agent response**

**Answer**

Ad hoc result: in June–July 2026, **2,886** flights left BOS for Europe. Of those, **2,872** were scheduled passenger flights (class F). The Snapshot ends in July 2026, so August 2026 is missing and this covers only two of the three summer months.

| Month (2026) | All departures to Europe | Scheduled passenger (F) |
|---|---|---|
| June | 1432 | 1425 |
| July | 1454 | 1447 |
| **Jun–Jul total** | **2,886** | **2,872** |

**Why**

- The query summed `departures_performed` from T-100 for origin BOS to Europe-coded destination countries, with the total computed in SQL.
- The gap between the two columns is small. It is non-passenger service (cargo and charter), and nearly all of it is passenger flying.
- For the last full summer, the Snapshot has June, July and August 2025. Those months show 1432, 1480 and 1485 departures to Europe, 1423, 1471 and 1466 of them class F. I did not total them.

**Assumptions & scope**

- "Last summer" is June–August of the most recent year, which is 2026. August is not yet in the Snapshot.
- "Flights" means departures performed, all carriers and all service classes. The class F column is the passenger-only view.
- Europe uses the standard ISO-2 country list. Turkey (TR) is excluded.
- Counts are segments departing BOS, not unique routes or passengers.

**Data Confidence**

Medium, because this is an ad-hoc query outside the scoring methodology. Source: BTS T-100 Segment (All Carriers), as of Jul 2026, with a 24-month window from Aug 2024 to Jul 2026.

*13 s, $0.036*
