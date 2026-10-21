"use client";

import { Cell, Pie, PieChart } from "recharts";

import { type ChartConfig, ChartContainer } from "@/components/ui/chart";
import type { RouteMixData, Share } from "@/lib/contracts";
import { fmtInt, fmtPct } from "@/lib/format";
import { ChartFigure } from "./chart-figure";

const DONUT_CONFIG = {
  longHaul: { label: "Long-haul", color: "color-mix(in oklab, var(--ink) 82%, transparent)" },
  rest: { label: "Shorter", color: "var(--hairline-strong)" },
} satisfies ChartConfig;

type VariantKey = "passenger_departures" | "passenger_weighted" | "cargo_inclusive_departures";

const VARIANTS: { key: VariantKey; label: string; basis: string }[] = [
  { key: "passenger_departures", label: "Passenger flights", basis: "departures · class F" },
  { key: "passenger_weighted", label: "Passenger-weighted", basis: "by passengers" },
  { key: "cargo_inclusive_departures", label: "Cargo-inclusive", basis: "departures · all classes" },
];

export interface DonutVariant {
  key: VariantKey;
  label: string;
  basis: string;
  share: Share;
}

/** The labelled long-haul variants the tool returned with a non-empty base (passenger first, then the others). */
export function routeMixVariants(data: RouteMixData): DonutVariant[] {
  return VARIANTS.flatMap((v) => {
    const share = data[v.key];
    return share && share.total > 0 ? [{ ...v, share }] : [];
  });
}

const SIZE = 92;

/** A small donut: the long-haul arc is the tool's share_pct, drawn against the full circle. */
function Donut({ variant, primary }: { variant: DonutVariant; primary: boolean }) {
  const pct = Math.min(100, Math.max(0, variant.share.share_pct));
  // Arc geometry only; the number shown is the tool's share_pct, formatted.
  const slices = [
    { name: "longHaul", value: pct },
    { name: "rest", value: 100 - pct },
  ];
  return (
    <li className="flex min-w-0 flex-col items-center gap-1.5 text-center" data-testid={`donut-${variant.key}`}>
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <ChartContainer
          config={DONUT_CONFIG}
          className="aspect-square"
          style={{ width: SIZE, height: SIZE }}
          initialDimension={{ width: SIZE, height: SIZE }}
        >
          <PieChart accessibilityLayer={false} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              innerRadius={SIZE / 2 - 11}
              outerRadius={SIZE / 2 - 1}
              startAngle={90}
              endAngle={-270}
              stroke="none"
              isAnimationActive={false}
            >
              {slices.map((s) => (
                <Cell key={s.name} fill={`var(--color-${s.name})`} />
              ))}
            </Pie>
          </PieChart>
        </ChartContainer>
        <span
          className={`num pointer-events-none absolute inset-0 flex items-center justify-center text-[14px] ${primary ? "font-semibold" : "font-medium"}`}
        >
          {fmtPct(variant.share.share_pct)}
        </span>
      </div>
      <div className="min-w-0 leading-tight">
        <div className={`text-[12px] ${primary ? "font-semibold" : "font-medium"}`}>{variant.label}</div>
        <div className="text-[11px] text-[var(--ink-muted)]">{variant.basis}</div>
      </div>
    </li>
  );
}

/** Long-haul vs the rest, one donut per labelled variant the data allows. */
export function RouteMixDonuts({ data }: { data: RouteMixData }) {
  const variants = routeMixVariants(data);
  if (variants.length === 0) return null;
  return (
    <ChartFigure
      caption={`Long-haul (≥ ${fmtInt(data.min_miles)} mi) vs the rest`}
      tableNote="Values in the variant table below"
      testId="route-mix-donuts"
      legend={
        <ul className="flex gap-3 text-[11.5px] text-[var(--ink-muted)]">
          <li className="inline-flex items-center gap-1">
            <span aria-hidden className="inline-block size-2 rounded-full" style={{ background: DONUT_CONFIG.longHaul.color }} />
            Long-haul
          </li>
          <li className="inline-flex items-center gap-1">
            <span aria-hidden className="inline-block size-2 rounded-full" style={{ background: DONUT_CONFIG.rest.color }} />
            Shorter
          </li>
        </ul>
      }
    >
      <ul className="grid grid-cols-3 gap-2">
        {variants.map((v, i) => (
          <Donut key={v.key} variant={v} primary={i === 0 && v.key === "passenger_departures"} />
        ))}
      </ul>
    </ChartFigure>
  );
}
