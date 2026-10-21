import type { ConfidenceLevel, ToolResult } from "@/lib/contracts";

const levelColor: Record<ConfidenceLevel, string> = {
  High: "var(--ok)",
  Medium: "var(--warn)",
  Low: "var(--bad)",
};

export function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  return (
    <span
      className="num inline-flex items-center gap-1.5 rounded-[6px] border px-2 py-0.5 text-xs"
      style={{ borderColor: levelColor[level], color: levelColor[level] }}
    >
      <span aria-hidden className="size-1.5 rounded-full" style={{ background: levelColor[level] }} />
      Data Confidence: {level}
    </span>
  );
}

export function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="num inline-flex rounded-[6px] border border-[var(--hairline)] px-2 py-0.5 text-xs text-[var(--ink-muted)]">
      {children}
    </span>
  );
}

/** Data Confidence badge, As-of/window chips, Assumptions and caveats: shared by every renderer. */
export function EvidenceMeta({ result }: { result: ToolResult<unknown> }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <ConfidenceBadge level={result.data_confidence.level} />
        {result.coverage && (
          <Chip>
            Coverage {result.coverage.measured}/{result.coverage.of}
          </Chip>
        )}
        {result.ad_hoc && <Chip>ad hoc</Chip>}
        {result.sources.map((s) => (
          <Chip key={s.name + s.as_of}>
            As of {s.as_of}
            {s.window ? ` · ${s.window}` : ""}
          </Chip>
        ))}
      </div>
      {result.data_confidence.reasons.length > 0 && (
        <p className="text-xs text-[var(--ink-muted)]">{result.data_confidence.reasons.join(" · ")}</p>
      )}
      {(result.assumptions.length > 0 || result.caveats.length > 0) && (
        <div>
          <h4 className="num mb-1 text-xs font-medium uppercase tracking-[0.06em] text-[var(--ink-muted)]">
            Assumptions and caveats
          </h4>
          <ul className="list-disc space-y-1 pl-5 text-[13px]">
            {result.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
            {result.caveats.map((c) => (
              <li key={c} className="text-[var(--ink-muted)]">
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}
      <ul className="text-xs text-[var(--ink-muted)]">
        {result.sources.map((s) => (
          <li key={s.url}>
            Source:{" "}
            <a className="underline underline-offset-2" href={s.url} target="_blank" rel="noreferrer">
              {s.name}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
