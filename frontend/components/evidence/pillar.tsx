import type { PillarName } from "@/lib/contracts";

export const PILLARS: Record<PillarName, { label: string; short: string; letter: string; color: string }> = {
  momentum: { label: "Demand Momentum", short: "Mom.", letter: "M", color: "var(--pillar-momentum)" },
  pressure: { label: "Capacity Pressure", short: "Press.", letter: "P", color: "var(--pillar-pressure)" },
  scale: { label: "Market Scale", short: "Scale", letter: "S", color: "var(--pillar-scale)" },
};

/** A Pillar name with its consistent hue swatch (the swatch is decoration; the text carries the meaning). */
export function PillarKey({ pillar, short, letter }: { pillar: PillarName; short?: boolean; letter?: boolean }) {
  const p = PILLARS[pillar];
  return (
    <span className="inline-flex items-center gap-1" title={p.label}>
      <span aria-hidden className="inline-block size-2 rounded-[2px]" style={{ background: p.color }} />
      {letter ? (
        <abbr className="no-underline" title={p.label}>
          {p.letter}
          <span className="sr-only"> ({p.label})</span>
        </abbr>
      ) : short ? (
        <abbr className="no-underline" title={p.label}>
          {p.short}
        </abbr>
      ) : (
        p.label
      )}
    </span>
  );
}
