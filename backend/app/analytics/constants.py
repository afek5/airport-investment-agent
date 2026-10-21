"""All thresholds, weights and the alias table live here (HANDOFF P1-B)."""

from __future__ import annotations

from app.contracts import Weights

DEFAULT_WEIGHTS = Weights()  # momentum 0.35, pressure 0.40, scale 0.25

# Long-haul Flight (GLOSSARY): a segment of 3,000 statute miles or more.
LONG_HAUL_MILES = 3000

# T-100 service classes (SPEC §3). "Passenger flights" means F.
PASSENGER_CLASS = "F"
SERVICE_CLASS_LABELS = {
    "F": "scheduled passenger",
    "G": "scheduled cargo",
    "L": "non-scheduled passenger/cargo (charter)",
    "P": "non-scheduled cargo/other",
}
# All-cargo service classes (scheduled + non-scheduled freighters). L (charter) is mixed, so it is
# non-passenger but not all-cargo.
ALL_CARGO_CLASSES = ("G", "P")
# Above this share of non-class-F departures, route_mix adds the cargo-hub caveat.
CARGO_HEAVY_SHARE_PCT = 25.0
TOP_DESTINATIONS = 10

T100_SOURCE_NAME = "BTS T-100 Segment (All Carriers)"
T100_URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45"
FAA_ENPL_SOURCE_NAME = "FAA CY2025 commercial-service enplanements"
FAA_ENPL_URL = ("https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/"
                "arp-cy2025-commercial-service-enplanements.xlsx")

# resolve_airports alias table: lower-case phrase → (primary IATA, alternates, note).
AIRPORT_ALIASES: dict[str, tuple[str, list[str], str]] = {
    "la": ("LAX", ["BUR", "LGB", "ONT", "SNA"], "LA = LAX (Los Angeles International); SNA is Santa Ana/Orange County"),
    "los angeles": ("LAX", ["BUR", "LGB", "ONT", "SNA"], "Los Angeles = LAX; SNA is Santa Ana/Orange County"),
    "santa ana": ("SNA", [], "Santa Ana = SNA (John Wayne/Orange County)"),
    "orange county": ("SNA", [], "Orange County = SNA (John Wayne/Orange County)"),
    "john wayne": ("SNA", [], "John Wayne = SNA"),
    "sf": ("SFO", ["OAK", "SJC"], "SF = SFO (San Francisco International)"),
    "san francisco": ("SFO", ["OAK", "SJC"], "San Francisco = SFO"),
    "bay area": ("SFO", ["OAK", "SJC"], "Bay Area = SFO (alternates OAK, SJC)"),
    "anchorage": ("ANC", [], "Anchorage = ANC (Ted Stevens Anchorage International)"),
    "boston": ("BOS", ["MHT", "PVD"], "Boston = BOS (Logan)"),
    "logan": ("BOS", [], "Logan = BOS"),
    "new york": ("JFK", ["LGA", "EWR"], "New York = JFK (alternates LGA, EWR)"),
    "nyc": ("JFK", ["LGA", "EWR"], "NYC = JFK (alternates LGA, EWR)"),
    "chicago": ("ORD", ["MDW"], "Chicago = ORD (alternate MDW)"),
    "washington": ("DCA", ["IAD", "BWI"], "Washington = DCA (alternates IAD, BWI)"),
    "dc": ("DCA", ["IAD", "BWI"], "DC = DCA (alternates IAD, BWI)"),
    "houston": ("IAH", ["HOU"], "Houston = IAH (alternate HOU)"),
    "dallas": ("DFW", ["DAL"], "Dallas = DFW (alternate DAL)"),
    "hartford": ("BDL", [], "Hartford = BDL (Bradley International)"),
    "providence": ("PVD", [], "Providence = PVD"),
    "manchester": ("MHT", [], "Manchester (NH) = MHT"),
    "portland maine": ("PWM", [], "Portland, Maine = PWM"),
    "burlington": ("BTV", [], "Burlington (VT) = BTV"),
}

# ───────────────────────── Investment Opportunity Score (SPEC §4, ADR 0002) ─────────────────────────

# metric key → (Pillar, weight in Pillar, label, unit). Order is the display order.
METRICS: dict[str, tuple[str, float, str, str]] = {
    "forecast_cagr": ("momentum", 0.60, "FAA TAF forecast enplanement CAGR, FY2024→FY2035", "% / yr"),
    "enpl_yoy": ("momentum", 0.40, "Enplanement growth, CY2024→CY2025", "%"),
    "load_factor": ("pressure", 0.40, "Load Factor, scheduled passenger flights (class F), last 12 T-100 months", "%"),
    "delay_share": ("pressure", 0.30, "Departures delayed ≥15 min, last 12 On-Time months", "%"),
    "taxi_out": ("pressure", 0.30, "Average taxi-out, last 12 On-Time months", "min"),
    "enplanements": ("scale", 0.70, "Enplanements, CY2025", "passengers"),
    "metro_pop": ("scale", 0.30, "Metro (CBSA) population, 2025", "people"),
}
PILLARS = ("momentum", "pressure", "scale")
PILLAR_LABELS = {"momentum": "Demand Momentum", "pressure": "Capacity Pressure", "scale": "Market Scale"}
N_METRICS = len(METRICS)

IMPUTED_PERCENTILE = 50.0  # missing metrics sit at the median (disclosed, never silent)
PILLAR_FLOOR = 1.0  # ln(max(pillar, 1)) in the geometric mean

TAF_BASE_FY = 2024  # last actual fiscal year in TAF 2025
TAF_HORIZON_FY = 2035  # forecast_cagr horizon
TAF_GAP_FY = 2030  # Unmet Demand Forecast Gap horizon

T100_WINDOW_MONTHS = 12
ONTIME_WINDOW_MONTHS = 12
# Below this many reporting-carrier departures in the On-Time window, delay_share and taxi_out are null.
MIN_ONTIME_DEPARTURES = 1000

# Data Confidence from Coverage (measured metrics out of 7).
HIGH_COVERAGE = 7
MEDIUM_MIN_COVERAGE = 5

MISSING_REASONS = {
    "forecast_cagr": "no FAA TAF FY2024→FY2035 enplanement record",
    "enpl_yoy": "no FAA CY2024 enplanements to compare CY2025 with",
    "load_factor": "no scheduled passenger (class F) seats in T-100",
    "delay_share": "no On-Time coverage: fewer than 1,000 reporting-carrier departures",
    "taxi_out": "no On-Time coverage: fewer than 1,000 reporting-carrier departures",
    "enplanements": "no FAA CY2025 enplanements",
    "metro_pop": "no CBSA population: airport is outside a metro/micro area or unmatched",
}

SCREENING_CAVEAT = (
    "The Investment Opportunity Score is a screening signal: it identifies airports worth investigating and "
    "does not establish that a terminal renovation would be profitable (it has no project cost, terminal or gate "
    "utilisation, commercial revenue or feasibility data)."
)
ONTIME_SCOPE_CAVEAT = (
    "On-Time data covers only the largest (reporting) US carriers and domestic flights, so delay and taxi-out "
    "say nothing about international operations."
)

HUB_SIZE_ALIASES = {
    "l": "L", "large": "L", "large hub": "L",
    "m": "M", "medium": "M", "medium hub": "M",
    "s": "S", "small": "S", "small hub": "S",
    "n": "N", "nonhub": "N", "non-hub": "N", "non hub": "N",
}

# Snapshot sources (fallback names when the manifest lacks them).
SOURCE_NAMES = {
    "airports": "FAA CY2025 commercial-service airports + OurAirports",
    "enplanements": "FAA CY2025 commercial-service enplanements",
    "taf": "FAA Terminal Area Forecast 2025",
    "t100_routes": T100_SOURCE_NAME,
    "ontime_airport_month": "BTS Reporting Carrier On-Time Performance",
    "metro_population": "Census PEP CBSA population estimates",
    "runway_capacity": "FAA Airport Capacity Profiles (2014), hand-coded",
}

# ───────────────────────── compare_airports (congestion lens) ─────────────────────────

CONGESTION_INDEX_METRICS = ("delay_share", "taxi_out", "nas_delay_min_per_flight")

# ───────────────────────── Unmet Demand (SPEC §4) ─────────────────────────

HIGH_LF = 0.85  # route-months above this Load Factor count as "full"
# Spill Scenario buckets: (LF lower bound exclusive, upper bound inclusive, low rate, high rate).
SPILL_BUCKETS: tuple[tuple[float, float, float, float], ...] = (
    (0.85, 0.90, 0.02, 0.05),
    (0.90, 0.95, 0.05, 0.10),
    (0.95, float("inf"), 0.10, 0.15),
)
SPILL_TOP_ROUTES = 5
SPILL_LABEL = "Spill Scenario under assumed spill rates; not calibrated"
# IFR vs VFR arrival-rate drop → driver strength (0–100): a 50 % drop is as strong as the top percentile.
IFR_DROP_STRENGTH_PER_PCT = 2.0
# A Constraint Evidence item becomes a why-driver when its strength exceeds the national median.
DRIVER_MIN_STRENGTH = 50.0
# Indicators that only point at a constraint when positive (passengers outgrowing seats).
DRIVER_REQUIRES_POSITIVE = ("pax_minus_seat_growth_pp",)

CANNOT_DETERMINE = [
    "Actual denied or turned-away passengers (no public data records them).",
    "Demand that recaptured to nearby airports (e.g. OAK/SJC for SFO).",
    "Whether the binding constraint is the terminal, the gates or the runway/airspace.",
    "Airline network choices versus infrastructure limits.",
    "Project cost and revenue.",
]

# ───────────────────────── query_snapshot guard ─────────────────────────

QUERY_ROW_CAP = 200
QUERY_TIMEOUT_S = 5.0
