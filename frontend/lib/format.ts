// Display formatting for tool values. The UI formats numbers; it never derives new ones.

const intFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const decFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const oneFmt = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const DASH = "—";

export function fmtInt(n: number | null | undefined): string {
  return n == null || Number.isNaN(n) ? DASH : intFmt.format(n);
}

/** A 0–100 percentage, one decimal (tools round to one decimal already). */
export function fmtPct(n: number | null | undefined): string {
  return n == null || Number.isNaN(n) ? DASH : `${oneFmt.format(n)}%`;
}

/** A score or percentile on the 0–100 scale, one decimal. */
export function fmtScore(n: number | null | undefined): string {
  return n == null || Number.isNaN(n) ? DASH : oneFmt.format(n);
}

/** A raw number as the tool gave it: grouped, up to two decimals (tools round already; the UI never re-rounds harder). */
export function fmtNum(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return DASH;
  return decFmt.format(n);
}

/** A raw value with its unit as the tool labelled it ("%" attaches, other units follow a space). */
export function fmtValue(n: number | null | undefined, unit?: string | null): string {
  if (n == null || Number.isNaN(n)) return DASH;
  if (!unit) return fmtNum(n);
  if (unit === "%") return fmtPct(n);
  if (unit.startsWith("%")) return `${fmtPct(n)}${unit.slice(1).replace(/\s+/g, "")}`; // "% / yr" → "3.1%/yr"
  if (unit === "$" || unit === "USD") return `$${fmtNum(n)}`;
  return `${fmtNum(n)} ${unit}`;
}

export function fmtSigned(n: number | null | undefined, formatter: (v: number) => string = fmtNum): string {
  if (n == null || Number.isNaN(n)) return DASH;
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${formatter(Math.abs(n))}`;
}

export function fmtDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "";
  return ms < 1000 ? `${Math.max(0, Math.round(ms))}ms` : `${(ms / 1000).toFixed(1)}s`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function fmtMonth(year: number, month: number): string {
  return `${MONTHS[month - 1] ?? month} ${year}`;
}

export const HUB_SIZE: Record<string, string> = { L: "Large hub", M: "Medium hub", S: "Small hub", N: "Nonhub" };
