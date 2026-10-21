// Fixture-driven tests for the Evidence charts (HANDOFF P4 item 1). The fixtures are the real ToolResult
// envelopes the plain-table tests use; the charts read the same contracts.ts types, and every chart sits
// beside the table that holds its values.
import { render, screen, within } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { EvidenceCard } from "@/components/evidence";
import { rankingPillarRows, scorecardPillarRows } from "@/components/evidence/pillar-charts";
import { routeMixVariants } from "@/components/evidence/route-mix-donut";
import type { RankingData, RouteMixData, ScorecardData, ToolResult } from "@/lib/contracts";
import rank from "./fixtures/rank_airports.json";
import routeMix from "./fixtures/route_mix.json";
import scorecard from "./fixtures/airport_scorecard.json";

const rankR = rank as ToolResult<RankingData>;
const routeR = routeMix as unknown as ToolResult<RouteMixData>;
const scoreR = scorecard as ToolResult<ScorecardData>;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

// jsdom has no layout, so Recharts' ResponsiveContainer would measure 0×0 and draw nothing. Give each chart
// box the size its wrapper asks for (the panel width when only a height is set).
beforeAll(() => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const box = this.parentElement?.style;
    const width = parseFloat(box?.width ?? "") || 340;
    const height = parseFloat(box?.height ?? "") || 200;
    return { width, height, top: 0, left: 0, right: width, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
  });
});
afterAll(() => vi.restoreAllMocks());

const PILLAR_FILLS = ["var(--color-momentum)", "var(--color-pressure)", "var(--color-scale)"];

/** The chart precedes its table in reading order, and the table stays in the accessibility tree. */
function expectChartBeforeTable(chart: HTMLElement, table: HTMLElement) {
  expect(chart.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(table.closest("[aria-hidden='true']")).toBeNull();
}

describe("ranking pillar bars", () => {
  it("maps every ranked airport's Pillar scores in rank order, unchanged", () => {
    const rows = rankingPillarRows(rankR.data);
    expect(rows.map((r) => r.iata)).toEqual(rankR.data.ranked.map((r) => r.iata));
    expect(rows[0]).toEqual({ iata: "BOS", momentum: 50.2, pressure: 86.1, scale: 95.3 });
    const hvn = rows.find((r) => r.iata === "HVN")!;
    expect(hvn).toEqual({ iata: "HVN", momentum: 91.1, pressure: 56.2, scale: 68.1 });
  });

  it("draws three Pillar-hued bars per airport beside the ranking table", () => {
    render(<EvidenceCard toolName="rank_airports" result={rankR} />);
    const chart = screen.getByRole("figure", { name: /Pillar scores by airport/ });
    expect(chart).toHaveAccessibleName(/Values in the table below/);
    const legend = within(chart).getByTestId("pillar-legend");
    for (const l of ["Demand Momentum", "Capacity Pressure", "Market Scale", "Median (50)"]) expect(legend).toHaveTextContent(l);
    expect(chart.querySelector(".recharts-reference-line-line")).not.toBeNull(); // the median at 50

    const bars = chart.querySelectorAll(".recharts-bar-rectangle path");
    expect(bars).toHaveLength(rankR.data.ranked.length * 3);
    const fills = new Set([...bars].map((b) => b.getAttribute("fill")));
    expect([...fills].sort()).toEqual([...PILLAR_FILLS].sort());
    // Airport codes label the category axis, in rank order.
    const ticks = [...chart.querySelectorAll(".recharts-yAxis-tick-labels text")].map((t) => t.textContent);
    expect(ticks).toEqual(rankR.data.ranked.map((r) => r.iata));

    expectChartBeforeTable(chart, screen.getByRole("table", { name: /Top 10 by score/ }));
  });

  it("skips a missing Pillar score instead of drawing a zero", () => {
    const r = clone(rankR);
    r.data.ranked[0].pillars.pressure = null;
    render(<EvidenceCard toolName="rank_airports" result={r} />);
    const chart = screen.getByRole("figure", { name: /Pillar scores by airport/ });
    expect(chart.querySelectorAll(".recharts-bar-rectangle path")).toHaveLength(rankR.data.ranked.length * 3 - 1);
    expect(rankingPillarRows(r.data)[0].pressure).toBeNull();
  });

  it("renders no chart for an empty ranking", () => {
    const r = clone(rankR);
    r.data.ranked = [];
    render(<EvidenceCard toolName="rank_airports" result={r} />);
    expect(screen.queryByTestId("ranking-pillar-chart")).toBeNull();
  });
});

describe("scorecard pillar chart", () => {
  it("maps the three Pillars in Momentum / Pressure / Scale order with the tool's scores", () => {
    const rows = scorecardPillarRows(scoreR.data.pillars);
    expect(rows.map((r) => r.pillar)).toEqual(["momentum", "pressure", "scale"]);
    for (const row of rows) expect(row.score).toBe(scoreR.data.pillars.find((p) => p.pillar === row.pillar)!.score);
  });

  it("draws one labelled bar per Pillar beside the metric table", () => {
    render(<EvidenceCard toolName="airport_scorecard" result={scoreR} />);
    const chart = screen.getByRole("figure", { name: /Pillar scores · 0–100/ });
    const bars = [...chart.querySelectorAll(".recharts-bar-rectangle path")];
    expect(bars.map((b) => b.getAttribute("fill"))).toEqual(PILLAR_FILLS);
    const labels = [...chart.querySelectorAll(".recharts-label-list text")].map((t) => t.textContent);
    const byPillar = Object.fromEntries(scoreR.data.pillars.map((p) => [p.pillar, p.score]));
    expect(labels).toEqual(["momentum", "pressure", "scale"].map((p) => (byPillar[p] as number).toFixed(1)));
    expectChartBeforeTable(chart, within(screen.getByTestId("scorecard")).getByRole("table"));
  });
});

describe("route-mix donuts (G3, Anchorage)", () => {
  it("offers the passenger, passenger-weighted and cargo-inclusive variants, passenger first", () => {
    const v = routeMixVariants(routeR.data);
    expect(v.map((x) => x.key)).toEqual(["passenger_departures", "passenger_weighted", "cargo_inclusive_departures"]);
    expect(v.map((x) => x.share.share_pct)).toEqual([2.7, 6.2, 29.5]);
  });

  it("draws a long-haul vs the rest donut per variant with the tool's share in the centre", () => {
    render(<EvidenceCard toolName="route_mix" result={routeR} />);
    const chart = screen.getByRole("figure", { name: /Long-haul \(≥ 3,000 mi\) vs the rest/ });
    expect(within(chart).getByTestId("donut-passenger_departures")).toHaveTextContent("2.7%Passenger flights");
    expect(within(chart).getByTestId("donut-passenger_weighted")).toHaveTextContent("6.2%Passenger-weighted");
    expect(within(chart).getByTestId("donut-cargo_inclusive_departures")).toHaveTextContent("29.5%Cargo-inclusive");
    // Two arcs each: long-haul in ink, the rest in a hairline tone.
    const sectors = chart.querySelectorAll(".recharts-pie-sector path");
    expect(sectors).toHaveLength(6);
    expect(sectors[0].getAttribute("fill")).toBe("var(--color-longHaul)");
    expect(sectors[1].getAttribute("fill")).toBe("var(--color-rest)");
    expectChartBeforeTable(chart, screen.getByRole("table", { name: /Long-haul share by variant/ }));
  });

  it("leaves out a variant with no base (e.g. no passenger counts reported)", () => {
    const r = clone(routeR);
    r.data.passenger_weighted = { long_haul: 0, total: 0, share_pct: 0 };
    render(<EvidenceCard toolName="route_mix" result={r} />);
    expect(screen.queryByTestId("donut-passenger_weighted")).toBeNull();
    expect(screen.getByTestId("donut-cargo_inclusive_departures")).toBeInTheDocument();
  });
});
