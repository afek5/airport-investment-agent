import type { ConfidenceLevel, ToolResult } from "@/lib/contracts";
import { cn } from "@/lib/utils";

const levelVar: Record<ConfidenceLevel, string> = {
  High: "var(--ok)",
  Medium: "var(--warn)",
  Low: "var(--bad)",
};

/** Data Confidence badge: High = ok, Medium = warn, Low = bad; always with its text label. */
export function ConfidenceBadge({ level, compact }: { level: ConfidenceLevel; compact?: boolean }) {
  const c = levelVar[level] ?? "var(--ink-muted)";
  return (
    <span
      data-testid="confidence-badge"
      className="num inline-flex items-center gap-1.5 whitespace-nowrap rounded-[6px] border px-2 py-0.5 text-[11.5px] font-medium"
      style={{
        borderColor: `color-mix(in oklab, ${c} 55%, transparent)`,
        color: c,
        background: `color-mix(in oklab, ${c} 9%, transparent)`,
      }}
    >
      <span aria-hidden className="size-1.5 rounded-full" style={{ background: c }} />
      {compact ? "" : "Data Confidence: "}
      {level}
    </span>
  );
}

export function Chip({
  children,
  tone,
  title,
  wrap,
}: {
  children: React.ReactNode;
  tone?: "live" | "warn";
  title?: string;
  wrap?: boolean;
}) {
  return (
    <span
      title={title}
      className={cn(
        "num inline-flex max-w-full items-center gap-1 rounded-[6px] border px-2 py-0.5 text-[11.5px]",
        wrap ? "whitespace-normal break-words" : "whitespace-nowrap",
        tone === "live"
          ? "border-[color-mix(in_oklab,var(--live)_45%,transparent)] text-[var(--live-ink)]"
          : tone === "warn"
            ? "border-[color-mix(in_oklab,var(--warn)_55%,transparent)] text-[var(--warn)]"
            : "border-[var(--hairline-strong)] text-[var(--ink-muted)]",
      )}
    >
      {children}
    </span>
  );
}

/** Data Confidence, Coverage, As-of/window chips, Assumptions and caveats, sources: shared by every renderer. */
export function EvidenceMeta({ result, live }: { result: ToolResult<unknown>; live?: boolean }) {
  const asOf = dedupe(result.sources.map((s) => `${s.as_of}${s.window ? ` · ${s.window}` : ""}`));
  const sources = dedupeBy(result.sources, (s) => s.url || s.name);
  return (
    <div className="space-y-3 text-sm" data-testid="evidence-meta">
      <div className="flex flex-wrap items-center gap-1.5">
        <ConfidenceBadge level={result.data_confidence.level} />
        {result.coverage ? (
          <Chip title="Measured metrics out of the score's inputs">
            Coverage {result.coverage.measured}/{result.coverage.of}
          </Chip>
        ) : null}
        {result.ad_hoc ? (
          <Chip tone="warn" title="Ad-hoc result: not a scored tool">
            Ad hoc
          </Chip>
        ) : null}
        {live ? (
          <Chip tone="live" title="Fetched at question time; never changes a score">
            Live Signal
          </Chip>
        ) : null}
        {asOf.map((a) => (
          <Chip key={a} wrap>
            As of {a}
          </Chip>
        ))}
      </div>
      {result.data_confidence.reasons.length > 0 ? (
        <ul className="space-y-0.5 text-xs text-[var(--ink-muted)]" aria-label="Data Confidence reasons">
          {result.data_confidence.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : null}
      {result.assumptions.length > 0 ? (
        <div>
          <h4 className="eyebrow mb-1.5">Assumptions</h4>
          <ul className="list-disc space-y-1 pl-4 text-[13px] leading-[1.45] marker:text-[var(--ink-muted)]">
            {result.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {result.caveats.length > 0 ? (
        <div>
          <h4 className="eyebrow mb-1.5">Caveats</h4>
          <ul className="list-disc space-y-1 pl-4 text-[13px] leading-[1.45] text-[var(--ink-muted)]">
            {result.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {sources.length > 0 ? (
        <ul className="space-y-0.5 text-xs text-[var(--ink-muted)]">
          {sources.map((s) => (
            <li key={s.url || s.name}>
              Source:{" "}
              {s.url ? (
                <a className="underline decoration-[var(--hairline-strong)] underline-offset-2 hover:text-[var(--ink)]" href={s.url} target="_blank" rel="noreferrer">
                  {s.name}
                </a>
              ) : (
                s.name
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function dedupe(xs: string[]): string[] {
  return [...new Set(xs)];
}
function dedupeBy<T>(xs: T[], key: (x: T) => string): T[] {
  const seen = new Set<string>();
  return xs.filter((x) => (seen.has(key(x)) ? false : (seen.add(key(x)), true)));
}
