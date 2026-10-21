"use client";

import { useId } from "react";

import type { PillarName } from "@/lib/contracts";
import { PillarKey } from "./pillar";

/**
 * A chart that sits beside its table. The drawing is decoration for sighted readers: it is hidden from
 * assistive tech and kept out of the tab order, and the caption points to the table that holds every value
 * (UI-STYLE accessibility floor).
 */
export function ChartFigure({
  caption,
  legend,
  tableNote = "Values in the table below",
  testId,
  children,
}: {
  caption: React.ReactNode;
  legend?: React.ReactNode;
  tableNote?: string;
  testId?: string;
  children: React.ReactNode;
}) {
  const id = useId();
  return (
    <figure aria-labelledby={id} data-testid={testId} className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p id={id} className="eyebrow">
          {caption}
          <span className="sr-only">. {tableNote}.</span>
        </p>
        {legend ? <div aria-hidden="true">{legend}</div> : null}
      </div>
      <div aria-hidden="true">{children}</div>
    </figure>
  );
}

const ORDER: PillarName[] = ["momentum", "pressure", "scale"];

/** The median reference line (percentile 50) every Pillar chart draws. */
export const MEDIAN_STROKE = "color-mix(in oklab, var(--ink) 38%, transparent)";

function MedianKey() {
  return (
    <li className="inline-flex items-center gap-1">
      <span aria-hidden className="inline-block w-3 border-t border-dashed" style={{ borderColor: MEDIAN_STROKE }} />
      Median (50)
    </li>
  );
}

/** The three Pillar hues with their names (in the order every chart and table uses), plus the median line. */
export function PillarLegend({ pillars = true }: { pillars?: boolean }) {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px] text-[var(--ink-muted)]" data-testid="pillar-legend">
      {pillars
        ? ORDER.map((p) => (
            <li key={p}>
              <PillarKey pillar={p} />
            </li>
          ))
        : null}
      <MedianKey />
    </ul>
  );
}

/** Shared Recharts styling: mono, muted axis ticks; hairline grid; calm tooltip cursor. */
export const CHART_CLASS =
  "aspect-auto w-full [&_.recharts-cartesian-axis-tick-value]:fill-[var(--ink-muted)] [&_.recharts-cartesian-axis-tick-value]:font-mono [&_.recharts-cartesian-axis-tick-value]:text-[11px] [&_.recharts-cartesian-grid_line]:stroke-[var(--hairline)] [&_.recharts-rectangle.recharts-tooltip-cursor]:fill-[var(--tint)]";
