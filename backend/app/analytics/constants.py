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
