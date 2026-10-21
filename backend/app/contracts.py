"""Cross-package contracts (HANDOFF §2, SPEC §5).

Every agent tool returns the same envelope, `ToolResult[<Data>]`. The `data`
models below are mirrored in `frontend/lib/contracts.ts`; change both in one
commit and say so in the package report.

Numbers in `data` are the only numbers the agent may cite (the LLM never
computes). Percentages are 0–100 floats rounded to 1 decimal.
"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

# ───────────────────────────── envelope ─────────────────────────────

ConfidenceLevel = Literal["High", "Medium", "Low"]


class Source(BaseModel):
    name: str
    url: str
    as_of: str = Field(description="Latest period the figure describes, e.g. 'Jul 2026'")
    window: str | None = Field(default=None, description="Period actually used, e.g. '12 months, Aug 2025–Jul 2026'")


class DataConfidence(BaseModel):
    """About the evidence, never about investment success (GLOSSARY: Data Confidence)."""

    level: ConfidenceLevel
    reasons: list[str] = Field(default_factory=list)


class Coverage(BaseModel):
    measured: int
    of: int = 7


DataT = TypeVar("DataT", bound=BaseModel)


class ToolResult(BaseModel, Generic[DataT]):
    data: DataT
    sources: list[Source] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    data_confidence: DataConfidence
    coverage: Coverage | None = None
    caveats: list[str] = Field(default_factory=list)
    ad_hoc: bool = False


# ───────────────────────────── weights ─────────────────────────────


class Weights(BaseModel):
    """Pillar Weights. Defaults per SPEC §4; normalised to sum 1 before use."""

    momentum: float = Field(default=0.35, ge=0)
    pressure: float = Field(default=0.40, ge=0)
    scale: float = Field(default=0.25, ge=0)

    def normalised(self) -> Weights:
        total = self.momentum + self.pressure + self.scale
        if total <= 0:
            raise ValueError("weights must not all be zero")
        return Weights(momentum=self.momentum / total, pressure=self.pressure / total, scale=self.scale / total)


PillarName = Literal["momentum", "pressure", "scale"]
HubSize = Literal["L", "M", "S", "N"]

# ───────────────────────────── resolve_airports ─────────────────────────────


class AirportCandidate(BaseModel):
    iata: str
    name: str
    city: str
    state: str
    hub_size: str
    is_primary: bool = True
    match: str = Field(description="How it matched: code | alias | name")


class ResolveData(BaseModel):
    query: str
    resolved: str | None = Field(description="Best match IATA code, or None when nothing matched")
    candidates: list[AirportCandidate] = Field(default_factory=list)
    alternates: list[str] = Field(default_factory=list, description="Other plausible airports for the same name")


# ───────────────────────────── route_mix ─────────────────────────────


class Share(BaseModel):
    long_haul: int
    total: int
    share_pct: float


class ServiceClassRow(BaseModel):
    service_class: str
    label: str
    departures: int
    long_haul_departures: int
    passengers: int
    freight_lbs: int
    share_of_departures_pct: float = Field(description="This class's departures / all departures from the airport")
    long_haul_share_pct: float = Field(description="This class's long-haul departures / this class's departures")
    share_of_long_haul_pct: float = Field(description="This class's long-haul departures / all long-haul departures")


class LongHaulDestination(BaseModel):
    dest: str
    dest_country: str | None
    distance_mi: int
    departures: int
    passengers: int


class RouteMixData(BaseModel):
    iata: str
    airport_name: str
    min_miles: int
    include_cargo: bool
    window: str
    months: list[str]
    passenger_departures: Share = Field(description="Class F departures performed with distance ≥ min_miles (the headline Long-haul share)")
    passenger_weighted: Share = Field(description="Class F passengers on segments ≥ min_miles / all class F passengers")
    cargo_inclusive_departures: Share = Field(description="All service classes (F, G, L, P): labelled variant")
    non_passenger_departure_share_pct: float = Field(description="Share of all departures that are not class F (cargo + non-scheduled)")
    non_passenger_departures: Share = Field(description="Classes G, L and P together (everything except class F): long-haul / all their departures")
    all_cargo_departures: Share = Field(description="All-cargo classes G and P together: long-haul / all their departures")
    all_cargo_share_of_long_haul_pct: float = Field(description="Classes G + P long-haul departures / all long-haul departures (all classes)")
    non_passenger_share_of_long_haul_pct: float = Field(description="Classes G + L + P long-haul departures / all long-haul departures (all classes)")
    by_service_class: list[ServiceClassRow]
    top_long_haul_destinations: list[LongHaulDestination]


# ───────────────────────────── scoring (P1-B fills) ─────────────────────────────


class PillarScores(BaseModel):
    momentum: float | None
    pressure: float | None
    scale: float | None


class RankedAirport(BaseModel):
    rank: int
    iata: str
    name: str
    state: str
    hub_size: str
    score: float = Field(description="Investment Opportunity Score, 1–100")
    pillars: PillarScores
    coverage: Coverage
    provisional: bool
    imputed_metrics: list[str] = Field(default_factory=list)


class NotRankedAirport(BaseModel):
    iata: str
    name: str
    reason: str


class RankingData(BaseModel):
    scope: str
    states: list[str] | None = None
    faa_region: str | None = None
    hub_sizes: list[str] | None = None
    pillar: Literal["overall", "momentum", "pressure", "scale"] = "overall"
    weights: Weights
    universe_size: int
    ranked: list[RankedAirport]
    not_ranked: list[NotRankedAirport] = Field(default_factory=list)


class MetricRow(BaseModel):
    metric: str
    label: str
    pillar: PillarName
    raw_value: float | None
    unit: str
    percentile: float | None
    imputed: bool
    weight_in_pillar: float


class PillarBreakdown(BaseModel):
    pillar: PillarName
    score: float | None
    weight: float
    metrics: list[MetricRow]


class ScorecardData(BaseModel):
    iata: str
    name: str
    state: str
    hub_size: str
    weights: Weights
    score: float | None
    provisional: bool
    not_ranked_reason: str | None = None
    national_rank: int | None
    national_of: int
    hub_rank: int | None
    hub_of: int
    pillars: list[PillarBreakdown]
    imputed_metrics: list[str] = Field(default_factory=list)


class ComparisonMetric(BaseModel):
    key: str
    label: str
    unit: str
    values: dict[str, float | None] = Field(description="iata → raw value")
    percentiles: dict[str, float | None] = Field(default_factory=dict, description="iata → national percentile")


class ComparisonData(BaseModel):
    lens: Literal["congestion", "demand", "scorecard"]
    iatas: list[str]
    names: dict[str, str]
    metrics: list[ComparisonMetric]
    congestion_index: dict[str, float | None] | None = Field(
        default=None, description="Mean percentile of delay_share, taxi_out, nas_delay_min_per_flight; a lens, not the Investment Opportunity Score")


# ───────────────────────────── unmet_demand (P1-B fills) ─────────────────────────────


class EvidenceItem(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str
    benchmark: float | None = None
    benchmark_label: str | None = None
    source: str
    as_of: str
    strength: float | None = Field(default=None, description="Deterministic ordering key for why_drivers")


class ForecastGap(BaseModel):
    from_fy: int
    to_fy: int
    enplanements_from: float
    enplanements_to: float
    enplanements_abs: float
    enplanements_pct: float
    ops_from: float | None = None
    ops_to: float | None = None
    ops_abs: float | None = None
    ops_pct: float | None = None


class SpillRoute(BaseModel):
    dest: str
    months_over_threshold: int
    low: float
    high: float


class SpillScenario(BaseModel):
    label: str = "Spill Scenario under assumed spill rates; not calibrated"
    low: float
    high: float
    parameters: list[str]
    top_routes: list[SpillRoute] = Field(default_factory=list)


class UnmetDemandData(BaseModel):
    iata: str
    name: str
    constraint_evidence: list[EvidenceItem]
    forecast_gap: ForecastGap | None
    spill_scenario: SpillScenario | None
    cannot_determine: list[str]
    why_drivers: list[str]


# ───────────────────────────── live tools (P1-C fills) ─────────────────────────────


class LiveTrafficMonth(BaseModel):
    year: int
    month: int
    departures: int | None
    passengers: int | None
    seats: int | None
    load_factor_pct: float | None


class LiveTrafficData(BaseModel):
    iata: str
    months: list[LiveTrafficMonth]


class OdMarket(BaseModel):
    other_airport: str
    other_city: str | None = None
    nsmiles: float | None = None
    passengers_per_day: float | None = None
    fare: float | None = None
    carrier_lg: str | None = None
    large_ms_pct: float | None = None
    fare_lg: float | None = None
    carrier_low: str | None = None
    lf_ms_pct: float | None = None
    fare_low: float | None = None


class OdDemandData(BaseModel):
    iata: str
    year: int | None
    quarter: int | None
    markets: list[OdMarket]


class LiveDelay(BaseModel):
    iata: str
    kind: str = Field(description="e.g. Departure Delay, Ground Stop, Ground Delay Program, Closure")
    reason: str | None = None
    min_delay: str | None = None
    max_delay: str | None = None
    trend: str | None = None


class LiveDelaysData(BaseModel):
    update_time: str | None
    queried: list[str]
    delays: list[LiveDelay]
    no_active_delay: list[str] = Field(default_factory=list)


# ───────────────────────────── ad hoc ─────────────────────────────


class AdHocData(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


# ───────────────────────────── UI-only ─────────────────────────────


class FollowupsData(BaseModel):
    questions: list[str]
