# Example transcripts: golden questions G1–G6

Recorded from one live run of `make test-live` (real Claude, model `anthropic:claude-sonnet-5-5`, Snapshot built 2026-10-21T18:32:22Z). Every number in each answer passed the number-grounding check: it appears in a tool result of the same run. G5 is a follow-up in the G1 conversation. Regenerate with `WRITE_EXAMPLES=1 make test-live`.

Total model cost of the six answers: $0.25.

## G1. Which airports in New England are strong candidates for terminal expansion?

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"]})`
- `suggest_followups({"questions": ["What if growth matters twice as much for New England airports?", "Compare congestion at BOS, BTV and BGR", "Show the unmet demand picture at Bangor (BGR)"]})`

**Agent response**

**Answer**

I ranked New England (CT, ME, MA, NH, RI, VT) by Investment Opportunity Score at the default Pillar Weights. The table shows the top 10 of 16 ranked airports.

| Rank | Airport | Hub Size | Score | Demand Momentum | Capacity Pressure | Market Scale | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BOS Boston Logan | L | 73.1 | 50.2 | 86.1 | 95.3 | 7 of 7 |
| 2 | BGR Bangor | N | 72.4 | 85.7 | 75.9 | 53 | 7 of 7 |
| 3 | BTV Burlington | S | 71.9 | 69.4 | 82.8 | 60.4 | 7 of 7 |
| 4 | HVN New Haven | S | 69.9 | 91.1 | 56.2 | 68.1 | provisional, 5 of 7 |
| 5 | PWM Portland (ME) | S | 64.8 | 64.3 | 60.8 | 72.6 | 7 of 7 |
| 6 | PVD Providence | S | 62.8 | 65 | 51.8 | 81.6 | 7 of 7 |
| 7 | PSM Portsmouth (NH) | N | 60.1 | 57.9 | 64.6 | 56.4 | provisional, 5 of 7 |
| 8 | BDL Hartford Bradley | M | 57 | 41.2 | 59.8 | 83.5 | 7 of 7 |
| 9 | MVY Martha's Vineyard | N | 54.7 | 82.1 | 57.7 | 28.4 | 7 of 7 |
| 10 | MHT Manchester | S | 52.2 | 61.5 | 35.7 | 76.3 | 7 of 7 |

**Why**

The top three are close (73.1, 72.4, 71.9), and each is strong on different Pillars.
- **BOS:**
  - Market Scale is 95.3 and Capacity Pressure is 86.1.
  - Demand Momentum is only 50.2, the weakest of its three Pillars.
  - It is a large, congested airport where the case rests on strain and size rather than growth.
- **BGR:**
  - Demand Momentum is 85.7 and Capacity Pressure is 75.9.
  - Market Scale is 53, because it is a nonhub airport.
  - It ranks highly on growth and load or delay strain, not on size.
- **BTV:** It is balanced, with Capacity Pressure of 82.8, Demand Momentum of 69.4 and Market Scale of 60.4.
- **HVN (fourth):**
  - It has the highest Demand Momentum in the region, at 91.1.
  - Its Capacity Pressure is 56.2, and that figure is provisional.

**Assumptions & scope**
- New England is CT, ME, MA, NH, RI and VT.
- I used the default Pillar Weights: Demand Momentum 0.35, Capacity Pressure 0.40, Market Scale 0.25. I can re-run with different weights.
- HVN and PSM have provisional scores. Delay share and taxi-out were imputed at the median because they have fewer than 1,000 reporting-carrier departures. That pulls their Capacity Pressure toward the middle.
- On-Time data covers only reporting carriers' domestic flights, so delay and taxi-out say nothing about international operations.
- This is a screening list of candidates, not proof that an expansion would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.

**Data Confidence:** Medium.
- 8 of 10 listed airports have 7 of 7 Coverage.
- HVN and PSM are provisional at 5 of 7, with delay share and taxi-out imputed.
- Sources and windows:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: FY2024 actual to FY2035 forecast.
  - BTS T-100: Aug 2025–Jul 2026 (as of Jul 2026).
  - BTS On-Time: Sep 2025–Aug 2026 (as of Aug 2026).
  - Census population: Vintage 2025, 1 Jul 2025 estimate.

*12 s, $0.035*

---

## G2. Compare LA and Santa Ana airport congestion levels.

**Tool calls**

- `resolve_airports({"query": "LA"})`
- `resolve_airports({"query": "Santa Ana"})`
- `compare_airports({"iatas": ["LAX", "SNA"], "lens": "congestion"})`
- `live_delays({"iatas": ["LAX", "SNA"]})`
- `suggest_followups({"questions": ["Which of LAX and SNA scores higher on the Investment Opportunity Score?", "How much Unmet Demand evidence is there at SNA?", "Rank Southern California airports for terminal expansion"]})`

**Agent response**

**Answer**

LAX is more congested than SNA on the congestion lens. Its congestion_index is 57.5, against 50.1 for SNA. The gap comes from taxi-out time and runway intensity. The two airports have the same share of delayed departures. Neither has an active delay or ground stop right now.

| Metric | LAX | SNA |
|---|---|---|
| Departures delayed ≥15 min | 20.6% (pctile 58.5) | 20.6% (pctile 56.8) |
| Average taxi-out | 18.2 min (pctile 68.5) | 16.1 min (pctile 38.2) |
| Cancelled departures | 1% (pctile 17.8) | 1.1% (pctile 20.3) |
| NAS delay per departure | 3 min (pctile 45.6) | 3.5 min (pctile 55.2) |
| Departures per month, all T-100 classes | 22,265.6 (pctile 99) | 4,283 (pctile 88.5) |
| Departures per runway per day | 182.9 (pctile 98.5) | 70.4 (pctile 90.7) |
| Load factor, class F | 82.3% (pctile 90.5) | 79.8% (pctile 74.4) |
| Runways | 4 | 2 |
| **congestion_index** | **57.5** | **50.1** |

**Why**
- **Delays are a tie.** Both airports delay 20.6% of departures by 15 minutes or more.
- **Taxi-out favours SNA.** LAX averages 18.2 minutes (68.5th percentile) and SNA 16.1 minutes (38.2nd percentile).
- **Runway load favours SNA.** LAX handles 182.9 departures per runway per day, against 70.4 at SNA. SNA's 90.7th percentile still shows its two runways are busy by national standards.
- **Load factor is higher at LAX.** It is 82.3%, against 79.8% at SNA.
- **NAS delay and cancellations slightly favour LAX.** SNA is a little worse on NAS delay (3.5 vs 3 minutes) and cancellations (1.1% vs 1%).
- **Live Signal:** LAX has only a closure notice for non-scheduled transient general aviation, which doesn't affect airline operations. SNA has nothing active.

**Assumptions & scope**
- "LA" is read as LAX (Los Angeles International). The alternates were BUR, LGB and ONT, with SNA as Santa Ana/Orange County. Say if you meant one of those instead.
- Percentiles are national, among FAA Primary Airports that have each metric.
- congestion_index is the mean national percentile of delay share, taxi-out and NAS delay per departure. It is a congestion lens, not the Investment Opportunity Score.
- On-Time data covers only reporting carriers' domestic flights. Delay and taxi-out say nothing about international operations.
- Departures per month and per runway per day use all T-100 service classes and the OurAirports runway count.

**Data Confidence**

High, because every compared metric is measured for both airports.
- T-100 window: Aug 2025–Jul 2026 (as of Jul 2026).
- On-Time window: Sep 2025–Aug 2026 (as of Aug 2026).
- Live NAS Status: as of Wed Oct 21 21:33:54 2026 GMT.

*13 s, $0.041*

---

## G3. What is the percentage of long haul flights out of Anchorage airport?

**Tool calls**

- `route_mix({"iata": "ANC"})`
- `suggest_followups({"questions": ["How does ANC's long-haul share compare with SEA or SFO?", "Is ANC a strong candidate for terminal investment?", "What is ANC's latest monthly traffic?"]})`

**Agent response**

**Answer**

Long-haul Flight means a segment of 3,000 statute miles or more. At Anchorage (ANC), the share depends on which flights you count:

| Measure | Long-haul | Total | Share |
|---|---|---|---|
| (a) **Headline:** scheduled passenger departures (class F) | 1,005 | 37,243 | **2.7%** |
| (b) Passenger-weighted (passengers on long-haul segments ÷ class F passengers) | 166,414 | 2,699,637 | 6.2% |
| (c) Cargo-inclusive (all service classes, a labelled variant) | 25,743 | 87,249 | 29.5% |

**Why**

ANC is a cargo hub, so the cargo-inclusive share is far above the passenger share.
- Non-passenger flights (classes G, L and P) are 57.3% of all departures.
- All-cargo flights (classes G + P) make up 24,643 of the 25,743 long-haul departures. That is 95.7% of all long-haul departures.
- Scheduled cargo (G) has 16,234 long-haul departures out of 33,824, which is 48% of its departures. Non-scheduled cargo (P) has 8,409 out of 13,893, or 60.5%.
- Freighters stop at ANC between Asia and North America, and these segments are long-haul.
- Scheduled passenger service is only 42.7% of departures. Its long-haul flights are mostly US domestic routes to hubs: DFW (388 departures), ATL (156), IAH (128), IAD (110), EWR (101) and JFK (71). The international long-haul route with the most departures is FRA (30).

**Assumptions & scope**
- Window: 12 months, Aug 2025–Jul 2026, all carriers.
- Headline share counts class F departures performed from ANC. Cargo-inclusive counts classes F, G, L and P. Non-passenger means G, L and P. All-cargo means G and P, because L charters can carry passengers.
- T-100 reports flight segments, so a multi-stop flight counts each leg separately.
- The top-destinations list covers class F only.

**Data Confidence**
High. T-100 is a census of all carriers' segments. Source: BTS T-100 Segment (All Carriers), as of Jul 2026, 12 months from Aug 2025 to Jul 2026.

*12 s, $0.034*

---

## G4. What is the unmet flight demand in SFO airport and why?

**Tool calls**

- `unmet_demand({"iata": "SFO"})`
- `od_demand({"iata": "SFO"})`
- `suggest_followups({"questions": ["How does SFO compare with LAX and BOS on congestion?", "Are there any live delays or ground stops at SFO right now?", "What is SFO's Investment Opportunity Score and rank?"]})`

**Agent response**

**Answer**

The public data can't measure SFO's unmet demand directly, because no public data records turned-away passengers. The observed Constraint Evidence shows an airport under real strain. The FAA forecast adds a large Forecast Gap.

| Constraint Evidence | SFO | National median |
|---|---|---|
| Departures delayed ≥15 min | 25.3% | 20.0% |
| Average taxi-out | 23.0 min | 16.8 min |
| Load Factor, class F | 82.1% | 75.8% |
| Class F route-months with Load Factor above 0.85 | 35.2% | 18.6% |
| NAS delay per departure | 3.9 min | 3.3 min |

| Forecast Gap, FAA TAF FY2024 → FY2030 | From | To | Change |
|---|---|---|---|
| Total enplanements | 24,765,642 | 30,516,426 | 23.2% (5,750,784) |
| Air-carrier operations | 350,805 | 435,218 | 24.1% (84,413) |

**Why**

The drivers are listed by strength, which is SFO's national percentile on each indicator:
1. **Taxi-out:** 23.0 min against a median of 16.8 min, at the 96.3rd percentile. This points to congestion on the airfield.
2. **Load factor:** 82.1% against 75.8%, at the 89.4th percentile. Planes are fuller than at most airports.
3. **Delays:** 25.3% of departures are delayed 15 minutes or more, at the 88.4th percentile.
4. **Full routes:** 35.2% of route-months are above 0.85 load factor, at the 83.4th percentile. The routes most often above the threshold are EWR (12 months), JFK (10), ORD (10), DFW (10) and HNL (9).
5. **Weather resilience:** The FAA Airport Capacity Profile (2019) gives SFO an arrival rate of 54/hr in visual conditions and 36/hr in instrument conditions. That is a 33.3% drop in bad weather.
6. **NAS delay:** 3.9 min per departure, a modest excess (64.7th percentile).

Supply is not clearly lagging demand. Passenger growth was 0.6% against seat growth of 0.7%, and the difference of -0.1 pp compares with a national median of -0.9 pp.

Market side (DOT airfare data, 2026 Q1):
- **Biggest markets:** LAX (4,717.5 passengers a day), JFK (3,721.4) and EWR (2,941.4).
- **Transcontinental fares:** about $494.88 to JFK, $571.7 to EWR and $412.23 to BOS.
- **Carrier concentration:** UA holds 86.1% of the EWR market and 69.5% of ORD. Lower-fare carriers hold only 11.4% of EWR and 27.6% of ORD.
- **Reading:** high fares and concentrated carriers fit a market with limited capacity. They don't prove it.

**Spill Scenario** (a scenario under assumed spill rates, not calibrated and not observed): assuming spill rates of 2–15% on class F route-months above 0.85 load factor, the tool returns a range of 396,415 to 839,701 passengers. The rates are illustrative and not calibrated to SFO or to any booking data. Full aircraft alone do not prove that anyone was turned away.

**Assumptions & scope**
- "SFO" is San Francisco International.
- Benchmarks are national medians of FAA Primary Airports.
- On-Time data covers only large reporting carriers and domestic flights. Delay and taxi-out say nothing about international operations.
- The airfare report covers only large contiguous-US domestic city-pair markets. It is one quarter of data from the DB1B 10% ticket sample.
- The IFR/VFR figures are from 2019 and are static.
- **What the data can't tell us:**
  - Actual denied or turned-away passengers.
  - Demand that recaptured to nearby airports such as OAK or SJC.
  - Whether the binding constraint is the terminal, the gates or the runway and airspace.
  - Airline network choices versus infrastructure limits.
  - Project cost and revenue.
- This is a screening view, not proof that an investment would be profitable.

**Data Confidence: Medium**
- Unmet Demand is argued from observed indicators and an official forecast. Turned-away passengers are not observed in any public data.
- The Spill Scenario rests on assumed, uncalibrated spill rates.
- The airfare data covers one quarter.
- Windows:
  - T-100: Aug 2025–Jul 2026.
  - On-Time: Sep 2025–Aug 2026.
  - FAA TAF 2025: actuals to FY2024, forecast to FY2030.
  - Capacity profile: 2019.
  - DOT airfare report: 2026 Q1.

*16 s, $0.047*

---

## G5. What if growth matters twice as much?

*(Follow-up in the G1 conversation.)*

**Tool calls**

- `rank_airports({"states": ["CT", "ME", "MA", "NH", "RI", "VT"], "weights": {"momentum": 0.7, "pressure": 0.4, "scale": 0.25}})`
- `suggest_followups({"questions": ["What if congestion matters twice as much instead?", "Show the full scorecard for Bangor (BGR)", "Compare demand momentum at BGR, HVN and BTV"]})`

**Agent response**

**Answer**

I doubled the Demand Momentum weight and left the others at their defaults. The weights are Demand Momentum 0.7, Capacity Pressure 0.4 and Market Scale 0.25, which the tool normalised to 0.52, 0.30 and 0.19. BGR now ranks first and BOS drops from first to fourth.

| New rank | Airport | Score | Demand Momentum | Capacity Pressure | Market Scale | Previous rank | Coverage |
|---|---|---|---|---|---|---|---|
| 1 | BGR | 75.6 | 85.7 | 75.9 | 53 | 2 | 7 of 7 |
| 2 | HVN | 74.8 | 91.1 | 56.2 | 68.1 | 4 | provisional, 5 of 7 |
| 3 | BTV | 71.3 | 69.4 | 82.8 | 60.4 | 3 | 7 of 7 |
| 4 | BOS | 66.4 | 50.2 | 86.1 | 95.3 | 1 | 7 of 7 |
| 5 | PWM | 64.7 | 64.3 | 60.8 | 72.6 | 5 | 7 of 7 |
| 6 | PVD | 63.4 | 65 | 51.8 | 81.6 | 6 | 7 of 7 |
| 7 | MVY | 60.8 | 82.1 | 57.7 | 28.4 | 9 | 7 of 7 |
| 8 | PSM | 59.5 | 57.9 | 64.6 | 56.4 | 7 | provisional, 5 of 7 |
| 9 | BID | 57.4 | 96.2 | 32.4 | 33.7 | not in the previous top 10 | provisional, 5 of 7 |
| 10 | WST | 57.4 | 96 | 32.7 | 33.3 | not in the previous top 10 | provisional, 5 of 7 |

**Why**
- **Who moved up:**
  - HVN moved up two places. Its Demand Momentum of 91.1 is the highest among the airports in the top 8.
  - MVY moved up two places on Demand Momentum of 82.1.
  - BID and WST entered the top 10 on Demand Momentum of 96.2 and 96.
- **Who moved down:**
  - BOS's Demand Momentum is the lowest of its three Pillars, at 50.2. Its strengths are Market Scale (95.3) and Capacity Pressure (86.1), so it falls from first to fourth.
  - BDL and MHT dropped out of the top 10. Their Demand Momentum was 41.2 and 61.5 in the first run. I didn't re-query them.
- **BGR and BTV:** they hold up because they are strong on more than one Pillar.
- **BID and WST:** their Capacity Pressure is about 32 and their Market Scale about 33, so they score well mainly on growth.

**Assumptions & scope**
- "Growth matters twice as much" means doubling the Demand Momentum weight only. I can re-run with a different interpretation.
- HVN, PSM, BID and WST have provisional scores. Delay share and taxi-out were imputed at the median because they have fewer than 1,000 reporting-carrier departures. BID and WST are tiny nonhub airports whose high growth percentiles probably come from a small base.
- The scores are a screening list, not proof that an expansion would be profitable. The Snapshot has no project cost, terminal or gate utilisation, commercial revenue or feasibility data.
- On-Time data covers only reporting carriers' domestic flights.

**Data Confidence:** Medium.
- 6 of 10 listed airports have 7 of 7 Coverage.
- HVN, PSM, BID and WST are provisional at 5 of 7, with delay share and taxi-out imputed.
- Sources and windows are the same as in the first answer:
  - FAA enplanements: CY2024–CY2025.
  - FAA TAF 2025: FY2024 actual to FY2035 forecast.
  - BTS T-100: Aug 2025–Jul 2026.
  - BTS On-Time: Sep 2025–Aug 2026.
  - Census: Vintage 2025.

*12 s, $0.064*

---

## G6. How many flights left BOS for Europe last summer?

**Tool calls**

- `query_snapshot({"sql": "SELECT year, month, SUM(departures_performed) AS departures FROM t100_routes WHERE origin='BOS' GROUP BY year, month ORDER BY year DESC, month DESC LIMIT 6"})`

  ```sql
  SELECT year, month, SUM(departures_performed) AS departures FROM t100_routes WHERE origin='BOS' GROUP BY year, month ORDER BY year DESC, month DESC LIMIT 6
  ```

- `query_snapshot` (long arguments)

  ```sql
  SELECT service_class, month, SUM(departures_performed) AS departures FROM t100_routes WHERE origin='BOS' AND year=2026 AND month IN (6,7) AND dest_country IN ('AD','AL','AT','BA','BE','BG','BY','CH','CY','CZ','DE','DK','EE','ES','FI','FR','GB','GI','GR','HR','HU','IE','IS','IT','LI','LT','LU','LV','MC','MD','ME','MK','MT','NL','NO','PL','PT','RO','RS','SE','SI','SK','SM','UA','XK') GROUP BY ROLLUP (service_class, month) ORDER BY service_class, month
  ```

- `suggest_followups({"questions": ["Which European cities had the most departures from BOS in June–July 2026?", "What is BOS's long-haul share of departures?", "How does BOS compare with JFK and EWR on congestion?"]})`

**Agent response**

**Answer**

For the summer months the Snapshot has (June and July 2026), **2,886** flights left BOS for Europe. This is an ad hoc result.

| Service class | June 2026 | July 2026 | Jun–Jul total |
|---|---|---|---|
| F, scheduled passenger | 1,425 | 1,447 | 2,872 |
| L, non-scheduled passenger/cargo (charter) | 7 | 7 | 14 |
| **All classes** | | | **2,886** |

**Why**

- Almost all of the total is scheduled passenger service. Class F accounts for 2,872 of the 2,886 departures, and charters add only 14.
- The figures are T-100 `departures_performed`, which counts flights actually flown, not flights scheduled.

**Assumptions & scope**

- "Last summer" means June–August of the most recent year in the Snapshot, which is 2026. The Snapshot ends in July 2026, so **August 2026 is missing**. The count covers only June and July and understates a full summer.
- "Europe" uses the system's ISO-2 country list. Turkey (TR) is excluded, and I can include it if you want.
- "Flights" means departures from BOS to a European destination, counted across all carriers and all service classes. The scheduled passenger (class F) figure is shown separately. The sum is returned by the SQL rollup.
- The query was one SELECT over `t100_routes`, filtered to origin BOS, year 2026, months 6 and 7.

**Data Confidence**

Medium. The query is ad hoc and sits outside the scoring methodology, and the SQL and months should be checked. Source: BTS T-100 Segment (all carriers), as of Jul 2026, covering 24 months from Aug 2024 to Jul 2026.

*13 s, $0.030*
