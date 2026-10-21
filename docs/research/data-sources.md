# Airport Investment Intelligence Agent: verified data-source inventory

> **Note for builders:** this report was written in a scratch folder. The samples it calls `research/dl/` are now in `data/raw/` (renamed where noted: FAA xlsx → `faa_cy2025_commercial_enplanements.xlsx`). The scripts are in `docs/research/scripts/`.

Tested from this machine on **2026-10-20**. Samples are in `research/dl/`, scripts in `research/scripts/`.
Legend: **LIVE API** means a real HTTP API you can call while answering a question (JSON/XML, filterable, fast). **BULK** means a file or form download that you snapshot ahead of time.

Example questions: **Q1** New England terminal-expansion candidates · **Q2** LAX vs SNA congestion · **Q3** % long-haul out of ANC · **Q4** SFO unmet demand and why.

---

## A. Summary table

| # | Source | Type | Key? | Latest period (verified) | Fetched? | Serves |
|---|---|---|---|---|---|---|
| 1a | BTS SODA `r495-tyji` (T-100 segment summary by origin airport) | **LIVE API** | No (an app token is optional and raises throttle limits) | **Apr 2026** (updated 2026-07-16), back to 2014 | Yes, <1 s | Q1 Q2 Q3 Q4 |
| 1b | BTS TranStats T-100 Segment (All Carriers) via form POST | BULK (scriptable) | No | **Jul 2026** | Yes, 12 s, 564 KB zip per month | Q1 Q3 Q4 |
| 2a | DOT Consumer Airfare Report (SODA `tfrh-tu9e`, Table 1a airport pairs; also Table 6 `yj5y-b2ir`) | **LIVE API** | No | **2026 Q1** (updated 2026-09-03) | Yes | Q4 (fares/O&D demand) |
| 2b | BTS DB1B Market/Ticket/Coupon (10% ticket sample) | BULK | No | **2025 Q2 (stale, 15+ months)** | Yes (CA subset, 68 s) | Q4 |
| 3 | BTS Reporting Carrier On-Time Performance | BULK (PREZIP or POST) | No | **Aug 2026** | Yes (POST, 224 s) | Q2 Q4 |
| 4 | FAA CY passenger boardings (enplanements) xlsx | BULK (static URL) | No | **CY2025 final** (page updated 2026-10-06) | Yes, 58 KB | Q1 Q2 Q4 (hub class) |
| 5a | FAA ATADS / OPSNET (tower operations) | Web form only | No | form lists FY2027 | **Form replay failed (HTTP 500)** | (Q2) |
| 5b | FAA ASPM | Login wall | Yes (FAA account) | n/a | Redirect loop to LoginSys.asp | none |
| 6 | FAA NAS Status `nasstatus.faa.gov/api/airport-status-information` | **LIVE API** (XML) | No | real time | Yes | Q2 (live) |
| 7 | FAA capacity benchmarks / runway capacity | PDF only | n/a | 2014 benchmark report | Not machine-readable | Q2 Q4 (manual constants) |
| 8 | OurAirports `airports.csv` | BULK (static CSV, updated nightly) | No | nightly | Yes, 12.7 MB | all (metadata, geo, state) |
| 9 | OpenSky Network REST | **LIVE API** (limited) | Anonymous works for `/states`; `/flights` needs an account | real time | `/states/all` yes, `/flights/*` 403/404 anonymously | Q2 (live traffic snapshot) |
| 10 | AviationStack, AirLabs, AeroDataBox, FlightAware AeroAPI | LIVE API | **Key required** (all confirmed 401/400 without one) | real time | Not tested beyond auth | optional extras |
| 11a | Census API (ACS/PEP) | LIVE API | **Key now required** (302 to missing_key.html) | ACS 2024 | Blocked without key | Q1 Q4 |
| 11b | Census PEP CBSA population CSV | BULK (static) | No | **Vintage 2025** (2020–2025) | Yes, 827 KB | Q1 Q4 |
| 11c | BEA API | LIVE API | **Key required** | n/a | Error without key | Q1 Q4 |
| 11d | BEA regional bulk zips (CAGDP1 county GDP) | BULK | No | **2024** (released 2026-02-05) | Yes, 1.9 MB | Q1 Q4 |
| 12 | FAA Terminal Area Forecast (TAF) 2025 zip | BULK (static) | No | history to FY2024, forecast FY2025–**2055** | Yes, 15.7 MB in 1.8 s | Q1 Q4 (growth) |

---

## B. Source details

### 1a. BTS SODA: T-100 Segment Summary by Origin Airport (the main live API)
- Endpoint: `https://data.bts.gov/resource/r495-tyji.json` (Socrata SODA 2.x with SoQL `$select/$where/$group/$order`)
- Auth: none. Without an app token you get a shared IP throttle. A free Socrata app token (`X-App-Token`) avoids it. I hit no limits.
- Granularity: origin airport × month. Columns include `total_departures, total_passengers, total_seats, total_load_factor, total_distance_flight_sm` (average stage length), and domestic, outbound-international and inbound-international splits of each. It also has freight/mail lbs and `origin_city_name`.
- Coverage: Jan 2014 to **Apr 2026** (131,739 rows). It lags TranStats by about 3 months.
- Sample (verified):
  ```
  SFO 2026-04 deps 15753 pax 2,147,010 seats 2,669,813 LF 80.4 avg dist 1881 intl-out pax 583,559
  LAX 2026-04 deps 21793 pax 2,875,734 seats 3,571,137 LF 80.5
  SNA 2026-04 deps  4201 pax   452,129 seats   561,072 LF 80.6 avg dist 756
  ```
- Server-side aggregation works, e.g. annual pax for New England in about 1 s: BOS 21.28M→21.11M, PVD 1.99M→2.12M (+6.6%), MHT 0.63M→0.69M (+8.2%), PWM 1.22M→1.29M, BTV 0.67M→0.71M, BDL flat (2024→2025).
- Limitation: airport-level only, with **no route or distance distribution**. For Q3 you need 1b.
- Related charts on data.bts.gov (`tqbz-sck3`, `mi6s-4k3t`, `xb4z-t72k`) are views of this table. Separately, `3xj5-daif` "T100 Preliminary Estimates" is a national total only.

### 1b. BTS TranStats T-100 Segment (All Carriers, domestic + international) by scripted POST
- Form: `https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45` (ASP.NET). Domestic-only is `FIM`.
- Method: GET the page to read `__VIEWSTATE`, `__VIEWSTATEGENERATOR` and `__EVENTVALIDATION`. Then POST `cboGeography=All`, `cboYear=2026`, `cboPeriod=7` (month or `All`), `btnDownload=Download` and each wanted field name set to `on`. **Verified**: `scripts/transtats_dl.py` returned a 564 KB zip (3 MB CSV, 48,247 rows) for July 2026 in 12 s. You can also download a whole year in one request.
- Fields: `DEPARTURES_SCHEDULED, DEPARTURES_PERFORMED, SEATS, PASSENGERS, FREIGHT, DISTANCE, AIR_TIME, CARRIER, ORIGIN, DEST, *_STATE_ABR, *_COUNTRY, AIRCRAFT_TYPE, AIRCRAFT_CONFIG, CLASS, YEAR, MONTH, DISTANCE_GROUP …`
- Latest: "Latest Available Data: **July 2026**".
- Sample rows:
  ```
  DEPARTURES_SCHEDULED,DEPARTURES_PERFORMED,SEATS,PASSENGERS,DISTANCE,CARRIER,ORIGIN,ORIGIN_STATE_ABR,DEST,DEST_STATE_ABR,AIRCRAFT_TYPE,YEAR,MONTH,CLASS
  0.00,0.00,0.00,0.00,0.00,ABX,CVG,KY,CVG,KY,626,2026,7,P
  ```
- KPIs computed from the July 2026 sample:
  - **ANC**: 9,087 departures performed, of which 2,103 (**23.1%**) were ≥3,000 mi. Passengers: 393,566 total, 36,213 (**9.2%**) on ≥3,000 mi segments. ANC is a cargo hub, so filter `CLASS in ('F')` (scheduled passenger) or `AIRCRAFT_CONFIG=1` to get a passenger-only answer. Long-haul freighters otherwise dominate the departure count.
  - Scheduled-service load factor (CLASS F+L): LAX 0.851, SFO 0.829, BOS 0.852, SNA 0.776.
- Serves Q3 directly (distance mix), Q1 (seat growth, LF), and Q4 (LF by route; departures scheduled vs. performed).

### 2a. DOT Consumer Airfare Report (O&D demand plus fares, a live API)
- Endpoint: `https://data.transportation.gov/resource/tfrh-tu9e.json` (Table 1a, all US airport-pair markets). Table 6 (`yj5y-b2ir`) covers city pairs with ≥10 pax/day, and Table 2 (`wqw2-rjgd`) covers the top 1,000 city pairs.
- Auth: none. Latest is **2026 Q1** (about 2,080 airport pairs per quarter), derived from DB1B.
- Fields: `year, quarter, airport_1, airport_2, city1, city2, nsmiles, passengers` (average daily O&D pax), `fare, carrier_lg, large_ms, fare_lg, carrier_low, lf_ms, fare_low`.
- Sample:
  ```
  2026 Q1 LAX-SFO 379 mi  4,718 pax/day  avg fare $172  UA 33% share  low-fare WN $149
  2026 Q1 JFK-SFO 2619 mi 3,721 pax/day  avg fare $495  DL 44%
  2026 Q1 EWR-SFO 2619 mi 2,941 pax/day  avg fare $572  UA 86% share
  ```
- Use for Q4: high fare per mile, high carrier concentration (`large_ms`) and high load factor together point to suppressed or unmet demand. This is **the freshest O&D data publicly available**, and it is newer than the raw DB1B download.

### 2b. BTS DB1B (Airline Origin & Destination Survey, 10% ticket sample)
- PREZIP: `https://transtats.bts.gov/PREZIP/Origin_and_Destination_Survey_DB1B{Market|Ticket|Coupon}_{YYYY}_{Q}.zip` (about 90–110 MB per quarter).
- POST form: `gnoyr_VQ=FHK` (Market), `FKF` (Ticket), `FLM` (Coupon). `cboPeriod` is the quarter, and `cboGeography=<State name>` filters by state (origin or destination).
- **Latest: 2025 Q2 ("Latest Available Data: June 2025")**. 2025_3 through 2026_1 return 404. A stray 1.1 GB file `Origin_and_Destination_Survey_DB1CTicket_2026_3.zip` (dated 2026-06-11) exists in PREZIP and looks like a new or replacement product. I did not open it.
- Verified: a CA-filtered 2025 Q2 Market POST took 68 s and returned 1.84M rows / 69 MB CSV, with LAX the top origin. Note that requested field names which don't exist (`MKT_FARE`, `MKT_DISTANCE`, `MKT_COUPONS`) were **silently dropped**. Use the exact names from the form checkbox list.
- Verdict: skip it for a 1-day build and use 2a instead.

### 3. BTS Reporting Carrier On-Time Performance (congestion and delays)
- PREZIP: `https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{YYYY}_{M}.zip` (no zero-padding). About 32 MB per month. **Aug 2026 is the latest** (Last-Modified 2026-10-19). 2026_9 returns 404.
- POST form `gnoyr_VQ=FGJ` also says "Latest Available Data: August 2026". Downloading 17 fields for one month took **224 s** and produced a 7.4 MB zip (56 MB CSV, 608,388 flights).
- Useful fields: `DEP_DELAY, DEP_DEL15, ARR_DEL15, TAXI_OUT, TAXI_IN, CANCELLED, DIVERTED, NAS_DELAY, WEATHER_DELAY, CARRIER_DELAY, LATE_AIRCRAFT_DELAY, DEP_TIME_BLK`. TAXI_OUT and NAS_DELAY are the best airside-congestion proxies.
- KPIs computed for Aug 2026 departures:

  | Airport | Departures | % dep >15 min late | Avg taxi-out (min) | Cancel % |
  |---|---|---|---|---|
  | LAX | 16,494 | 21.8 | 19.1 | 0.81 |
  | SNA | 3,898 | 23.6 | 16.8 | 0.82 |
  | SFO | 13,560 | 31.9 | **27.8** | 0.73 |
  | BOS | 13,188 | 28.0 | 22.5 | 3.6 |
  | ANC | 2,383 | 20.4 | 12.8 | 0.88 |
- The data covers only the larger US carriers (reporting carriers) and domestic flights.
- data.bts.gov also has on-time charts (`rns4-gpqn`, `eaz9-4bny`, `hdqs-8yds`), but they sit on a national "Pocket Guide" table (`neuq-kfdt`), so they are **not usable per airport**.

### 4. FAA Passenger Boarding (Enplanement) data
- Page: `https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger` (last updated 2026-10-06). No bot blocking: plain curl returns 200.
- Direct URLs (verified 200):
  - `https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/arp-cy2025-commercial-service-enplanements.xlsx` (58 KB, 522 rows)
  - `.../arp-cy2025-all-enplanements.xlsx`, `.../ARP-CY2025-all-cargo-airports.xlsx` (PDFs are also available)
- Columns: `Rank, RO, ST, Locid, City, Airport Name, S/L, Hub (L/M/S/N), CY 25 Enplanements, CY 24 Enplanements, % Change`
  ```
  10 WP CA SFO San Francisco International  P L 26,251,850 25,078,968 +4.68%
  16 NE MA BOS Logan                        P L 21,021,153 21,090,721 -0.33%
  41 WP CA SNA John Wayne/Orange County     P M  5,521,729  5,370,273 +2.82%
  59 AL AK ANC Ted Stevens Anchorage        P M  2,729,285  2,767,856 -1.39%
  125 NE NH MHT Manchester Boston Regional  P S    685,594    633,257 +8.26%
  ```
- The page links only the current year. Older years live at different paths (historically `/sites/faa.gov/files/...`) and need a manual lookup. Each file already carries two years, which is enough for YoY growth.
- `openpyxl` is not installed here. `scripts/xlsx_peek.py` is a stdlib-only reader, or you can `pip install openpyxl`.

### 5. FAA ATADS (OPSNET) and ASPM
- ATADS: `https://www.aspm.faa.gov/opsnet/sys/Airport.asp` is public (no login) and lists data through FY2027. The page builds a raw SQL string in JavaScript (`select LOCID,YYYYMM,SUM(AC)… from tower_day where …`) and POSTs it to `opsnet-server-x.asp`. My replay returned **HTTP 500** even with a session cookie and every form default. Getting it working would need browser automation or more reverse-engineering. **Not recommended** for 1 day.
- Substitute for operations counts: TAF `AirportsOperations.xlsx` (history to FY2024), or T-100 `DEPARTURES_PERFORMED` ×2 for commercial ops.
- ASPM: `aspm.faa.gov/apm/...` loops through redirects to `LoginSys.asp`. It needs an FAA-issued account. **Unusable.**

### 6. FAA NAS Status API (live)
- `GET https://nasstatus.faa.gov/api/airport-status-information` returns XML (about 2.5 KB) with no key.
- Contents: `<Update_Time>`, then delay types: General Arrival/Departure Delay (ARPT, Reason, Min/Max, Trend), Ground Stops, Ground Delay Programs, and Airport Closures (with NOTAM text).
- Sample, 2026-10-20 15:15 GMT: `SFO`-area none; `ORD Departure 16–30 min WX:Low Ceilings Increasing`; `LGA Departure 15–29 WX:Wind`; closure NOTAMs for SNA, LAX, LAS, SAN.
- Only airports currently impacted appear in the response. If an airport is missing, it has no delay right now.
- The legacy `soa.smext.faa.gov/asws` endpoint is **dead** (DNS failure).
- Serves Q2 as a "right now" layer on top of historical KPIs.

### 7. Capacity benchmarks / runway capacity
- No machine-readable FAA source found. The *Airport Capacity Profiles* (2014) are PDF only, and ASPM's capacity rates (ADR/AAR) sit behind the login.
- Practical approach: hard-code called rates for the airports in scope (for example, published VMC/IMC hourly rates from the 2014 profiles) in a small `capacity.csv`, with a citation. Alternatively, derive a proxy from peak-hour departures in on-time data (`DEP_TIME_BLK` counts against max observed).
- TAF `Airports.xlsx` includes `OEP35` (core airport flag), `HUB_SIZE` and `ATCT_FLAG`.

### 8. OurAirports
- `https://davidmegginson.github.io/ourairports-data/airports.csv` (12.7 MB, about 80k rows, nightly). There is also `runways.csv` in the same repo (runway count and length, useful for capacity proxies). No key.
- Columns: `ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,scheduled_service,icao_code,iata_code,…`
- 873 US large or medium airports have an IATA code. New England (`iso_region` in US-MA/CT/RI/NH/VT/ME) gives 38, including BOS, BDL, PVD, MHT, PWM, BTV, BGR, ORH, HVN, ACK, MVY (MPV), HYA, PSM and others.
- Note: SNA and LAX are both in the LA MSA (31080). OurAirports gives no MSA, so use a county→CBSA crosswalk or a hand map.

### 9. OpenSky Network
- `GET https://opensky-network.org/api/states/all?lamin=..&lomin=..&lamax=..&lomax=..` works **anonymously** (200, `x-rate-limit-remaining: 399`). It returns live state vectors, for example aircraft on the ground at SFO.
- `GET /api/flights/departure|arrival?airport=KSFO&begin&end` anonymously gives **403 "You cannot access historical flights"** for windows more than 1 day old, and 404 (empty) for recent ones. An OAuth2 client account is required, and history is limited (about 30 days, 2–7 day windows per call per docs).
- Verdict: an optional "live traffic" tool only. Don't use it for KPIs.

### 10. Commercial flight APIs (all need keys, verified)
| API | Unauthenticated response | Free tier (vendor docs, **not verified today**) | Use |
|---|---|---|---|
| AviationStack `api.aviationstack.com/v1/flights` | `missing_access_key` | about 100 req/month, HTTP only on free tier | live or scheduled flights |
| AirLabs `airlabs.co/api/v9/schedules` | `Missing api_key` | about 1,000 req/month | schedules and routes |
| AeroDataBox (RapidAPI / api.market) | 401 / 400 | small monthly unit quota | airport delays and stats |
| FlightAware AeroAPI `aeroapi.flightaware.com/aeroapi` | 401 INVALID_API_KEY | pay-per-query (small monthly credit on personal tier) | airport delays, flights |

None is required. The free government sources cover every KPI, and these add quota risk.

### 11. Demand drivers
- **Census API** (`api.census.gov/data/2024/acs/acs1?...`) now **302-redirects to `missing_key.html`** without a key, so keyless use no longer works. The free key is instant, by email.
- **No-key substitute (verified):** `https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/cbsa-est2025-alldata.csv` (827 KB) with `CBSA, NAME, LSAD, POPESTIMATE2020..2025`. Sample: Boston MSA 4.92M→5.03M, SF MSA 4.75M→4.63M, LA 13.18M→12.84M, Anchorage 398k→406k.
- **BEA API** requires `UserID` (the `DEMO_KEY` value is rejected). The **no-key substitute (verified)** is `https://apps.bea.gov/regional/zip/CAGDP1.zip` (county real GDP 2001–2024, 1.9 MB). Roll it up to MSA with a county→CBSA crosswalk. `MAGDP.zip` returns an HTML page and is not a valid file. `SAGDP.zip` (state level, updated 2026-09-30) also exists.

### 12. FAA Terminal Area Forecast (TAF) 2025
- `https://taf.faa.gov/Downloads/APO100_TAF_Final_2025.zip` (15.7 MB, Last-Modified 2026-03-20, downloads in 2 s). The 2026 TAF is not out yet.
- Contents: `Airports.xlsx` (3,319 airports: LOCID, REGION, STATE, lat/lon, HUB_SIZE, OEP35, ATCT_FLAG…), `Enplanements.xlsx` (locid, scenario, ayear, aac, aat, commuter, us_flag, frgn_flag), `AirportsOperations.xlsx` (itn_ac, itn_at, itn_ga, itn_mil, loc_ga, loc_mil…), `BasedAircraft.xlsx`, `Tracon.xlsx`.
- `scenario=0` is historical (enplanements 1976–FY2024). `scenario=1` is the forecast FY2025–**FY2055**. Fiscal years run Oct to Sep.
- Sample: SFO air-carrier enplanements were 15.38M in 2024 and are forecast at 18.87M (2030), 23.13M (2040) and 28.04M (2050). SNA goes from 4.91M (2024) to 7.36M (2050). SFO itinerant air-carrier operations are forecast to go from 350,805 (2024) to 659,264 (2050).
- Total enplanements = `aac + aat + commuter`, plus `us_flag + frgn_flag` for international.
- Gotchas: `locid` is **space-padded** (`'SFO '`), so strip it. The xlsx files use inline strings with no sharedStrings.xml. The interactive site `taf.faa.gov` has no API.
- This is the best "growth" signal: the forecast CAGR set against current capacity.

---

## C. Which question uses what

| Question | KPIs | Sources |
|---|---|---|
| Q1 New England expansion candidates | enplanement YoY/3-yr growth (FAA CY xlsx, SODA), TAF 2024→2035 CAGR, load factor and seats growth (SODA), delay and taxi-out (on-time), MSA pop growth (PEP), hub size | 4, 1a, 12, 3, 11b, 8 |
| Q2 LAX vs SNA congestion | % dep delayed, avg taxi-out, NAS-delay minutes, cancels (on-time); departures per month and LF (SODA); live NAS status; ops vs capacity (TAF ops + hand-coded capacity) | 3, 1a, 6, 12, 7 |
| Q3 % long-haul ANC | departures and pax by `DISTANCE` bucket, filtered to `CLASS F` passenger | 1b (avg stage length only in 1a) |
| Q4 SFO unmet demand and why | LF by route (T-100), fares and concentration (Airfare Report), departures scheduled vs. performed, delays and taxi-out (capacity constraint), TAF forecast vs current ops, MSA pop/GDP | 1b, 2a, 3, 12, 11b/d |

---

## D. Recommended minimal source set (1-day build, all keyless)

**Live API tools, callable at question time:**
1. **BTS SODA `r495-tyji`**: airport-month passengers, seats, departures, LF, stage length and international split. A free Socrata app token is optional.
2. **DOT SODA `tfrh-tu9e`** (Consumer Airfare Report): O&D pax and fares by airport pair, current to 2026 Q1.
3. **FAA NAS Status API**: live delays, ground stops and closures.
4. (Optional) **OpenSky `/states/all`**: live aircraft counts near an airport, anonymous.

**Bulk snapshot, built once into SQLite/DuckDB by a `make data` script:**
5. **T-100 Segment All Carriers**, last 13–25 months via the scripted POST (about 0.5 MB zip per month, 12 s each). This provides route and distance mix and is needed for Q3.
6. **On-time performance**, last 3–12 months. Use the POST with about 15 columns (pre-aggregate to airport-month: % delayed, avg taxi-out, cancellations, NAS-delay min), or PREZIP. Keep only the aggregates.
7. **FAA CY2025 commercial-service enplanements xlsx**: hub class, CY24 vs CY25.
8. **FAA TAF 2025 zip**: history plus forecast to 2055, airport metadata.
9. **OurAirports airports.csv** (plus runways.csv): IATA↔ICAO, state, lat/lon, runway count.
10. **Census PEP CBSA 2025 CSV**, and optionally **BEA CAGDP1**, for demand drivers.

This gives a hybrid that holds up under the "use public APIs" requirement. Three government REST APIs are queried live, and the snapshot covers data that has no API (route-level T-100, on-time, TAF, FAA xlsx).

---

## E. Gotchas

- **The TranStats PREZIP host is very slow from here.** I measured about 43 KB/s (5 MB in 116 s), so one 32 MB on-time month takes about 12 min. The server-side POST with selected columns is faster per useful byte for T-100 (12 s). On-time POST still took about 4 min per month. Run downloads in the background and cache them. Don't download at question time.
- **TranStats forms are ASP.NET.** You must GET first for `__VIEWSTATE`/`__EVENTVALIDATION`. Unknown field names are silently ignored. Period values are month numbers (`7`) or quarters (`2`), and `cboGeography` takes a full state name.
- **The SODA T-100 summary lags TranStats** (Apr 2026 vs Jul 2026). State the data-as-of date in answers.
- **DB1B public download is frozen at 2025 Q2.** Use the Consumer Airfare Report SODA (2026 Q1) instead.
- **ANC long-haul is dominated by cargo.** Always filter T-100 `CLASS` (F = scheduled passenger, G = scheduled cargo, L/P = non-scheduled) and decide whether the question means passenger flights.
- **T-100 has zero-departure "P" rows** (for example ABX CVG→CVG). Filter `DEPARTURES_PERFORMED > 0`.
- **On-time data covers only the largest US carriers and domestic flights.** It does not show international delay at SFO or LAX.
- **Census and BEA APIs now need keys.** Use the static CSV/zip files instead, or register a free key (instant).
- **ATADS form replay returns 500, and ASPM needs a login.** Don't plan on FAA ops counts from them. Use TAF ops history (FY) or T-100 departures.
- **No machine-readable runway capacity exists.** Hand-code a small table with citations, or use a peak-hour-departures proxy.
- **TAF**: `locid` has trailing spaces, years are fiscal (Oct–Sep), and the files are inline-string xlsx (8 MB for operations). Parse once and store.
- **FAA enplanement xlsx**: the page links only the latest CY, and filenames change format year to year (`arp-cy2025-…` vs older `cy24-…`), so pin URLs in config.
- **NAS Status** lists only airports currently impacted. An empty result means "no active delay", not an error.
- **OpenSky anonymous** gives live states only. Historical flights return 403.
- **Commercial APIs** (AviationStack, AirLabs, AeroDataBox, AeroAPI) all need keys and have small free quotas. Avoid them for core KPIs.
- `openpyxl`/`pandas` are not installed in system Python here. Use a venv, or the stdlib readers in `research/scripts/`.

## F. Files
- Samples: `research/dl/` (t100seg_2026_07.zip, ontime_2026_08.zip, db1bmkt_2025q2_CA.zip, airports.csv, nas.xml, faa/cy2025_cs.xlsx, taf/taf2025.zip, cbsa2025.csv, bea/CAGDP1.zip, os_states.json, etc.)
- Scripts: `research/scripts/transtats_dl.py` (TranStats POST downloader, `GEO=<State>` env optional), `xlsx_peek.py`, `taf_extract.py`, `atads.py` (non-working ATADS replay, kept for reference)
