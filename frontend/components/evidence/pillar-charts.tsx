"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, XAxis, YAxis } from "recharts";

import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { PillarBreakdown, PillarName, RankingData } from "@/lib/contracts";
import { fmtScore } from "@/lib/format";
import { CHART_CLASS, ChartFigure, MEDIAN_STROKE, PillarLegend } from "./chart-figure";
import { PILLARS } from "./pillar";

/** Pillar hues from the UI-STYLE tokens; they switch with the theme because they are CSS variables. */
export const PILLAR_CHART_CONFIG = {
  momentum: { label: PILLARS.momentum.label, color: PILLARS.momentum.color },
  pressure: { label: PILLARS.pressure.label, color: PILLARS.pressure.color },
  scale: { label: PILLARS.scale.label, color: PILLARS.scale.color },
} satisfies ChartConfig;

const PILLAR_ORDER: PillarName[] = ["momentum", "pressure", "scale"];
const SCALE_TICKS = [0, 25, 50, 75, 100];

/** One row per ranked airport, the Pillar scores exactly as the tool returned them (rank order). */
export function rankingPillarRows(data: RankingData) {
  return data.ranked.map((r) => ({
    iata: r.iata,
    momentum: r.pillars.momentum,
    pressure: r.pillars.pressure,
    scale: r.pillars.scale,
  }));
}

/** One row per Pillar of a scorecard, in Momentum / Pressure / Scale order. */
export function scorecardPillarRows(pillars: PillarBreakdown[]) {
  return PILLAR_ORDER.flatMap((name) => {
    const p = pillars.find((x) => x.pillar === name);
    return p ? [{ pillar: name, label: PILLARS[name].label, score: p.score }] : [];
  });
}

const ROW_PX = 30; // three 6px bars plus breathing room per airport
const AXIS_PX = 22;

/** Grouped horizontal Pillar bars per ranked airport, on the shared 0–100 percentile scale. */
export function RankingPillarBars({ data }: { data: RankingData }) {
  const rows = rankingPillarRows(data);
  if (rows.length === 0) return null;
  const height = rows.length * ROW_PX + AXIS_PX;
  return (
    <ChartFigure caption="Pillar scores by airport · 0–100" legend={<PillarLegend />} testId="ranking-pillar-chart">
      <ChartContainer
        config={PILLAR_CHART_CONFIG}
        className={CHART_CLASS}
        style={{ height }}
        initialDimension={{ width: 340, height }}
      >
        <BarChart
          accessibilityLayer={false}
          data={rows}
          layout="vertical"
          margin={{ top: 0, right: 10, bottom: 0, left: 0 }}
          barCategoryGap={5}
          barGap={1}
        >
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            ticks={SCALE_TICKS}
            tickLine={false}
            axisLine={false}
            tickMargin={4}
            height={AXIS_PX - 4}
          />
          <YAxis
            type="category"
            dataKey="iata"
            width={38}
            tickLine={false}
            axisLine={false}
            tickMargin={6}
            interval={0}
          />
          <ReferenceLine x={50} stroke={MEDIAN_STROKE} strokeDasharray="3 3" ifOverflow="extendDomain" />
          <ChartTooltip
            cursor
            isAnimationActive={false}
            content={<ChartTooltipContent indicator="dot" formatter={tooltipValue} />}
          />
          {PILLAR_ORDER.map((p) => (
            <Bar key={p} dataKey={p} fill={`var(--color-${p})`} barSize={6} radius={[0, 2, 2, 0]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartFigure>
  );
}

/** The scorecard's three Pillar scores as labelled bars against the national median. */
export function ScorecardPillarChart({ pillars }: { pillars: PillarBreakdown[] }) {
  const rows = scorecardPillarRows(pillars);
  if (rows.length === 0) return null;
  const height = rows.length * 34 + AXIS_PX;
  return (
    <ChartFigure caption="Pillar scores · 0–100" legend={<PillarLegend pillars={false} />} testId="scorecard-pillar-chart">
      <ChartContainer
        config={PILLAR_CHART_CONFIG}
        className={`${CHART_CLASS} [&_.recharts-label-list_text]:font-mono [&_.recharts-label-list_text]:fill-[var(--ink)] [&_.recharts-yAxis-tick-labels_.recharts-cartesian-axis-tick-value]:font-sans [&_.recharts-yAxis-tick-labels_.recharts-cartesian-axis-tick-value]:text-[12px] [&_.recharts-yAxis-tick-labels_.recharts-cartesian-axis-tick-value]:fill-[var(--ink)]`}
        style={{ height }}
        initialDimension={{ width: 340, height }}
      >
        <BarChart
          accessibilityLayer={false}
          data={rows}
          layout="vertical"
          margin={{ top: 0, right: 34, bottom: 0, left: 0 }}
          barCategoryGap={8}
        >
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            ticks={SCALE_TICKS}
            tickLine={false}
            axisLine={false}
            tickMargin={4}
            height={AXIS_PX - 4}
          />
          <YAxis type="category" dataKey="label" width={132} tickLine={false} axisLine={false} tickMargin={8} interval={0} />
          <ReferenceLine x={50} stroke={MEDIAN_STROKE} strokeDasharray="3 3" ifOverflow="extendDomain" />
          <Bar dataKey="score" barSize={14} radius={[0, 3, 3, 0]} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.pillar} fill={`var(--color-${r.pillar})`} />
            ))}
            <LabelList dataKey="score" position="right" offset={6} fontSize={12} formatter={labelValue} />
          </Bar>
        </BarChart>
      </ChartContainer>
    </ChartFigure>
  );
}

function labelValue(v: unknown): string {
  return typeof v === "number" ? fmtScore(v) : "—";
}

function tooltipValue(value: unknown, name: unknown) {
  const key = String(name) as PillarName;
  const label = PILLARS[key]?.label ?? String(name);
  return (
    <div className="flex w-full items-center justify-between gap-3">
      <span className="flex items-center gap-1.5 text-[var(--ink-muted)]">
        <span aria-hidden className="inline-block size-2 rounded-[2px]" style={{ background: PILLARS[key]?.color }} />
        {label}
      </span>
      <span className="num text-[var(--ink)]">{typeof value === "number" ? fmtScore(value) : "—"}</span>
    </div>
  );
}
