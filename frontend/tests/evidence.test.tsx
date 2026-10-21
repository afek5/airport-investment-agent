// Fixture-driven tests: one per Evidence renderer. Fixtures in tests/fixtures/ are real ToolResult envelopes
// produced by the backend tools (Snapshot as of Jul/Aug 2026; the live ones fetched 2026-10-21).
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceCard, RENDERERS } from "@/components/evidence";
import type { ToolResult } from "@/lib/contracts";
import { EVIDENCE_TOOLS } from "@/lib/parts";
import adHoc from "./fixtures/query_snapshot.json";
import compare from "./fixtures/compare_airports.json";
import liveDelays from "./fixtures/live_delays.json";
import liveTraffic from "./fixtures/live_traffic.json";
import od from "./fixtures/od_demand.json";
import rank from "./fixtures/rank_airports.json";
import resolve from "./fixtures/resolve_airports.json";
import routeMix from "./fixtures/route_mix.json";
import scorecard from "./fixtures/airport_scorecard.json";
import unmet from "./fixtures/unmet_demand.json";

const FIXTURES: Record<string, ToolResult<unknown>> = {
  resolve_airports: resolve as ToolResult<unknown>,
  rank_airports: rank as ToolResult<unknown>,
  airport_scorecard: scorecard as ToolResult<unknown>,
  compare_airports: compare as ToolResult<unknown>,
  route_mix: routeMix as ToolResult<unknown>,
  unmet_demand: unmet as ToolResult<unknown>,
  live_traffic: liveTraffic as ToolResult<unknown>,
  od_demand: od as ToolResult<unknown>,
  live_delays: liveDelays as ToolResult<unknown>,
  query_snapshot: adHoc as ToolResult<unknown>,
};

const card = (name: string, result: ToolResult<unknown> = FIXTURES[name]) =>
  render(<EvidenceCard toolName={name} result={result} />);

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

describe("renderer registry", () => {
  it("has a renderer and a fixture for every Evidence tool", () => {
    for (const name of EVIDENCE_TOOLS) {
      expect(RENDERERS, name).toHaveProperty(name);
      expect(FIXTURES, name).toHaveProperty(name);
    }
  });

  it.each([...EVIDENCE_TOOLS])("%s renders tables plus the shared envelope metadata", (name) => {
    card(name);
    const el = screen.getByTestId(`evidence-${name}`);
    expect(within(el).getByTestId("confidence-badge")).toHaveTextContent(
      `Data Confidence: ${FIXTURES[name].data_confidence.level}`,
    );
    for (const s of FIXTURES[name].sources) expect(el).toHaveTextContent(`As of ${s.as_of}`);
    for (const a of FIXTURES[name].assumptions) expect(el).toHaveTextContent(a);
    for (const c of FIXTURES[name].caveats) expect(el).toHaveTextContent(c);
  });

  it("falls back to a readable note when a payload doesn't match its renderer", () => {
    const bad = { ...FIXTURES.rank_airports, data: { scope: "x" } } as ToolResult<unknown>;
    card("rank_airports", bad);
    expect(screen.getByText(/returned data this view can.t display/)).toBeInTheDocument();
    expect(screen.getByTestId("confidence-badge")).toBeInTheDocument();
  });
});

describe("route_mix (G3, Anchorage)", () => {
  it("shows the passenger share with the 3,000 mi definition and the labelled variants", () => {
    card("route_mix");
    expect(screen.getByRole("heading", { name: /ANC.*Long-haul share \(≥ 3,000 mi\)/ })).toBeInTheDocument();
    const rows = screen.getAllByRole("row").map((r) => r.textContent ?? "");
    expect(rows.find((r) => r.startsWith("Passenger flights (F)"))).toContain("2.7%");
    expect(rows.find((r) => r.startsWith("Passenger-weighted"))).toContain("6.2%");
    expect(rows.find((r) => r.startsWith("Cargo-inclusive"))).toContain("29.5%");
    expect(rows.find((r) => r.startsWith("Cargo-inclusive"))).toContain("25,743");
    expect(screen.getByText(/Ted Stevens Anchorage International · 12 months, Aug 2025–Jul 2026/)).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Top long-haul destinations" })).toBeInTheDocument();
  });
});

describe("rank_airports (G1, New England)", () => {
  it("renders the ranked table with Coverage and provisional marks", () => {
    card("rank_airports");
    const table = screen.getByRole("table", { name: /Top 10 by score/ });
    expect(within(table).getAllByRole("row")).toHaveLength(1 + 10);
    const hvn = within(table).getByText("HVN").closest("tr")!;
    expect(hvn).toHaveTextContent("5/7");
    expect(within(hvn).getByTitle("Provisional Score")).toBeInTheDocument();
    const bos = within(table).getByText("BOS").closest("tr")!;
    expect(within(bos).queryByTitle("Provisional Score")).toBeNull();
  });

  it("lists every Provisional Score with the imputed metrics by name", () => {
    card("rank_airports");
    const list = screen.getByTestId("provisional-list");
    expect(list).toHaveTextContent("HVN 5/7 · imputed: delay_share, taxi_out");
    expect(list).toHaveTextContent("PSM 5/7 · imputed: delay_share, taxi_out");
  });

  it("shows the weights and the scope", () => {
    card("rank_airports");
    expect(screen.getByText(/Weights: Momentum 0.35 · Pressure 0.40 · Scale 0.25/)).toBeInTheDocument();
  });

  it("lists airports that are not ranked", () => {
    const r = clone(FIXTURES.rank_airports) as ToolResult<{ not_ranked: unknown[] }>;
    r.data.not_ranked = [{ iata: "XYZ", name: "Example Field", reason: "no measured metric in Capacity Pressure" }];
    card("rank_airports", r);
    expect(screen.getByTestId("not-ranked")).toHaveTextContent("XYZ Example Field · no measured metric in Capacity Pressure");
  });
});

describe("airport_scorecard", () => {
  it("shows score, ranks and every metric grouped by Pillar", () => {
    card("airport_scorecard");
    const el = screen.getByTestId("scorecard");
    expect(el).toHaveTextContent("Investment Opportunity Score73.1");
    for (const p of ["Demand Momentum", "Capacity Pressure", "Market Scale"]) expect(within(el).getAllByText(p).length).toBeGreaterThan(0);
    const metricRows = (scorecard.data.pillars as { metrics: unknown[] }[]).reduce((n, p) => n + p.metrics.length, 0);
    expect(within(el).getByRole("table").querySelectorAll("tbody tr")).toHaveLength(metricRows + 3);
  });

  it("marks imputed metrics as missing and the score as provisional", () => {
    const r = clone(FIXTURES.airport_scorecard) as ToolResult<{
      provisional: boolean;
      imputed_metrics: string[];
      pillars: { metrics: { imputed: boolean; raw_value: number | null; percentile: number | null; label: string }[] }[];
    }>;
    const m = r.data.pillars[1].metrics[1];
    m.imputed = true;
    m.raw_value = null;
    m.percentile = 50;
    r.data.provisional = true;
    r.data.imputed_metrics = ["delay_share"];
    card("airport_scorecard", r);
    const row = screen.getByText(m.label).closest("tr")!;
    expect(row).toHaveTextContent("imputed");
    expect(row).toHaveTextContent("missing");
    expect(row).toHaveTextContent("50.0");
    expect(screen.getByText("Provisional")).toBeInTheDocument();
  });
});

describe("compare_airports (G2, congestion lens)", () => {
  it("puts both airports side by side with percentiles and the labelled congestion index", () => {
    card("compare_airports");
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: "LAX" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "SNA" })).toBeInTheDocument();
    const ci = within(table).getByText("Congestion index").closest("tr")!;
    expect(ci).toHaveTextContent("57.5");
    expect(ci).toHaveTextContent("50.1");
    expect(ci).toHaveTextContent("a lens, not the Investment Opportunity Score");
    expect(within(table).getByText("Cancelled departures")).toBeInTheDocument();
  });
});

describe("unmet_demand (G4, SFO)", () => {
  it("renders the three labelled blocks plus what the data can't tell us", () => {
    card("unmet_demand");
    const observed = screen.getByTestId("block-observed");
    expect(within(observed).getByText("Observed evidence")).toBeInTheDocument();
    expect(observed).toHaveTextContent("33.3%"); // IFR vs VFR arrival-rate drop
    const forecast = screen.getByTestId("block-forecast");
    expect(forecast).toHaveTextContent("FY2024");
    expect(forecast).toHaveTextContent("24,765,642");
    expect(forecast).toHaveTextContent("+5,750,784");
    const scenario = screen.getByTestId("block-scenario");
    expect(scenario).toHaveTextContent("not observed · not calibrated");
    expect(scenario).toHaveTextContent("Spill Scenario under assumed spill rates; not calibrated");
    expect(scenario).toHaveTextContent("396,415–839,701");
    const cannot = screen.getByTestId("block-cannot");
    expect(within(cannot).getAllByRole("listitem")).toHaveLength(unmet.data.cannot_determine.length);
    // Block order: observed first, scenario after the forecast.
    const order = ["block-observed", "block-forecast", "block-scenario", "block-cannot"].map((id) => screen.getByTestId(id));
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it("says so when there is no scenario or forecast", () => {
    const r = clone(FIXTURES.unmet_demand) as ToolResult<{ spill_scenario: null; forecast_gap: null }>;
    r.data.spill_scenario = null;
    r.data.forecast_gap = null;
    card("unmet_demand", r);
    expect(screen.getByTestId("block-scenario")).toHaveTextContent("no scenario");
    expect(screen.getByTestId("block-forecast")).toHaveTextContent("No FAA forecast");
  });
});

describe("live tools", () => {
  it("live_traffic lists months and is marked as a Live Signal", () => {
    card("live_traffic");
    const el = screen.getByTestId("evidence-live_traffic");
    expect(el).toHaveTextContent("Live Signal");
    expect(within(el).getByRole("table").querySelectorAll("tbody tr")).toHaveLength(liveTraffic.data.months.length);
    expect(el).toHaveTextContent("Nov 2025");
  });

  it("od_demand lists markets with passengers per day and fares", () => {
    card("od_demand");
    const row = screen.getByText("LAX").closest("tr")!;
    expect(row).toHaveTextContent("4,717.5");
    expect(row).toHaveTextContent("$172.46");
    expect(screen.getByText(/Q1 2026/)).toBeInTheDocument();
  });

  it("live_delays shows active programs and airports without delay", () => {
    card("live_delays");
    const el = screen.getByTestId("live-delays");
    expect(within(el).getByRole("table")).toHaveTextContent("LAX");
    const r = clone(FIXTURES.live_delays) as ToolResult<{ delays: unknown[]; no_active_delay: string[] }>;
    r.data.delays = [];
    r.data.no_active_delay = ["LAX", "SNA"];
    render(<EvidenceCard toolName="live_delays" result={r} />);
    expect(screen.getAllByTestId("live-delays")[1]).toHaveTextContent("No active delay at LAX, SNA");
  });
});

describe("query_snapshot (G6, ad hoc)", () => {
  it("shows the SQL, the rows and the ad-hoc mark", () => {
    card("query_snapshot");
    const el = screen.getByTestId("evidence-query_snapshot");
    expect(el).toHaveTextContent("SELECT dest_country");
    expect(within(el).getByText("Ad hoc")).toBeInTheDocument();
    expect(within(el).getByRole("table").querySelectorAll("tbody tr")).toHaveLength(adHoc.data.rows.length);
    expect(el).toHaveTextContent("29,691");
  });
});

describe("resolve_airports", () => {
  it("shows the resolved code, alternates and candidates", () => {
    card("resolve_airports");
    expect(screen.getByRole("heading", { name: /“LA” → LAX/ })).toBeInTheDocument();
    expect(screen.getByText(/Alternates: BUR, LGB, ONT, SNA/)).toBeInTheDocument();
  });
});
