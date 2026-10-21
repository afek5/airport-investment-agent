// TS mirror of backend/app/contracts.py (HANDOFF §2). Change both in one commit.
// Evidence renderers key on the tool name.

export type ConfidenceLevel = "High" | "Medium" | "Low";

export interface Source {
  name: string;
  url: string;
  as_of: string;
  window?: string | null;
}

export interface DataConfidence {
  level: ConfidenceLevel;
  reasons: string[];
}

export interface Coverage {
  measured: number;
  of: number;
}

export interface ToolResult<T> {
  data: T;
  sources: Source[];
  assumptions: string[];
  data_confidence: DataConfidence;
  coverage: Coverage | null;
  caveats: string[];
  ad_hoc: boolean;
}

export interface Weights {
  momentum: number;
  pressure: number;
  scale: number;
}

export type PillarName = "momentum" | "pressure" | "scale";

// resolve_airports
export interface AirportCandidate {
  iata: string;
  name: string;
  city: string;
  state: string;
  hub_size: string;
  is_primary: boolean;
  match: string;
}
export interface ResolveData {
  query: string;
  resolved: string | null;
  candidates: AirportCandidate[];
  alternates: string[];
}

// route_mix
export interface Share {
  long_haul: number;
  total: number;
  share_pct: number;
}
export interface ServiceClassRow {
  service_class: string;
  label: string;
  departures: number;
  long_haul_departures: number;
  passengers: number;
  freight_lbs: number;
}
export interface LongHaulDestination {
  dest: string;
  dest_country: string | null;
  distance_mi: number;
  departures: number;
  passengers: number;
}
export interface RouteMixData {
  iata: string;
  airport_name: string;
  min_miles: number;
  include_cargo: boolean;
  window: string;
  months: string[];
  passenger_departures: Share;
  passenger_weighted: Share;
  cargo_inclusive_departures: Share;
  non_passenger_departure_share_pct: number;
  by_service_class: ServiceClassRow[];
  top_long_haul_destinations: LongHaulDestination[];
}

// scoring (P1-B)
export interface PillarScores {
  momentum: number | null;
  pressure: number | null;
  scale: number | null;
}
export interface RankedAirport {
  rank: number;
  iata: string;
  name: string;
  state: string;
  hub_size: string;
  score: number;
  pillars: PillarScores;
  coverage: Coverage;
  provisional: boolean;
  imputed_metrics: string[];
}
export interface NotRankedAirport {
  iata: string;
  name: string;
  reason: string;
}
export interface RankingData {
  scope: string;
  states?: string[] | null;
  faa_region?: string | null;
  hub_sizes?: string[] | null;
  pillar: "overall" | PillarName;
  weights: Weights;
  universe_size: number;
  ranked: RankedAirport[];
  not_ranked: NotRankedAirport[];
}
export interface MetricRow {
  metric: string;
  label: string;
  pillar: PillarName;
  raw_value: number | null;
  unit: string;
  percentile: number | null;
  imputed: boolean;
  weight_in_pillar: number;
}
export interface PillarBreakdown {
  pillar: PillarName;
  score: number | null;
  weight: number;
  metrics: MetricRow[];
}
export interface ScorecardData {
  iata: string;
  name: string;
  state: string;
  hub_size: string;
  weights: Weights;
  score: number | null;
  provisional: boolean;
  not_ranked_reason?: string | null;
  national_rank: number | null;
  national_of: number;
  hub_rank: number | null;
  hub_of: number;
  pillars: PillarBreakdown[];
  imputed_metrics: string[];
}
export interface ComparisonMetric {
  key: string;
  label: string;
  unit: string;
  values: Record<string, number | null>;
  percentiles: Record<string, number | null>;
}
export interface ComparisonData {
  lens: "congestion" | "demand" | "scorecard";
  iatas: string[];
  names: Record<string, string>;
  metrics: ComparisonMetric[];
  congestion_index?: Record<string, number | null> | null;
}

// unmet_demand (P1-B)
export interface EvidenceItem {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  benchmark?: number | null;
  benchmark_label?: string | null;
  source: string;
  as_of: string;
  strength?: number | null;
}
export interface ForecastGap {
  from_fy: number;
  to_fy: number;
  enplanements_from: number;
  enplanements_to: number;
  enplanements_abs: number;
  enplanements_pct: number;
  ops_from?: number | null;
  ops_to?: number | null;
  ops_abs?: number | null;
  ops_pct?: number | null;
}
export interface SpillRoute {
  dest: string;
  months_over_threshold: number;
  low: number;
  high: number;
}
export interface SpillScenario {
  label: string;
  low: number;
  high: number;
  parameters: string[];
  top_routes: SpillRoute[];
}
export interface UnmetDemandData {
  iata: string;
  name: string;
  constraint_evidence: EvidenceItem[];
  forecast_gap: ForecastGap | null;
  spill_scenario: SpillScenario | null;
  cannot_determine: string[];
  why_drivers: string[];
}

// live tools (P1-C)
export interface LiveTrafficMonth {
  year: number;
  month: number;
  departures: number | null;
  passengers: number | null;
  seats: number | null;
  load_factor_pct: number | null;
}
export interface LiveTrafficData {
  iata: string;
  months: LiveTrafficMonth[];
}
export interface OdMarket {
  other_airport: string;
  other_city?: string | null;
  nsmiles?: number | null;
  passengers_per_day?: number | null;
  fare?: number | null;
  carrier_lg?: string | null;
  large_ms_pct?: number | null;
  fare_lg?: number | null;
  carrier_low?: string | null;
  lf_ms_pct?: number | null;
  fare_low?: number | null;
}
export interface OdDemandData {
  iata: string;
  year: number | null;
  quarter: number | null;
  markets: OdMarket[];
}
export interface LiveDelay {
  iata: string;
  kind: string;
  reason?: string | null;
  min_delay?: string | null;
  max_delay?: string | null;
  trend?: string | null;
}
export interface LiveDelaysData {
  update_time: string | null;
  queried: string[];
  delays: LiveDelay[];
  no_active_delay: string[];
}

// ad hoc
export interface AdHocData {
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
}

// UI-only
export interface FollowupsData {
  questions: string[];
}

export interface ToolDataByName {
  resolve_airports: ResolveData;
  route_mix: RouteMixData;
  rank_airports: RankingData;
  airport_scorecard: ScorecardData;
  compare_airports: ComparisonData;
  unmet_demand: UnmetDemandData;
  live_traffic: LiveTrafficData;
  od_demand: OdDemandData;
  live_delays: LiveDelaysData;
  query_snapshot: AdHocData;
}
