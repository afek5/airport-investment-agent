import type { ComparisonData } from "@/lib/contracts";
import { fmtScore, fmtValue } from "@/lib/format";
import { DataTable, EvidenceTitle, Muted, Td, Th, Tr } from "./table";

const LENS: Record<ComparisonData["lens"], string> = {
  congestion: "Congestion lens",
  demand: "Demand lens",
  scorecard: "Scorecard lens",
};

export function ComparisonEvidence({ data }: { data: ComparisonData }) {
  const ci = data.congestion_index;
  return (
    <div className="space-y-4" data-testid="comparison">
      <EvidenceTitle
        title={`${data.iatas.join(" vs ")} · ${LENS[data.lens] ?? data.lens}`}
        sub={data.iatas.map((i) => `${i} ${data.names[i] ?? ""}`.trim()).join(" · ")}
      />
      <DataTable caption="Value and national percentile (p)">
        <thead>
          <tr>
            <Th>Metric</Th>
            {data.iatas.map((i) => (
              <Th key={i} num>
                {i}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.metrics.map((m) => (
            <Tr key={m.key}>
              <Td>{m.label}</Td>
              {data.iatas.map((i) => (
                <Td key={i} num>
                  {fmtValue(m.values[i], m.unit)}
                  {m.percentiles[i] != null ? (
                    <div className="text-[11px] text-[var(--ink-muted)]">p{fmtScore(m.percentiles[i])}</div>
                  ) : null}
                </Td>
              ))}
            </Tr>
          ))}
          {ci ? (
            <Tr className="bg-[var(--tint)]">
              <Td className="font-medium">
                Congestion index
                <div className="text-[11px] font-normal text-[var(--ink-muted)]">
                  mean percentile of delay share, taxi-out, NAS delay; a lens, not the Investment Opportunity Score
                </div>
              </Td>
              {data.iatas.map((i) => (
                <Td key={i} num className="font-semibold">
                  {ci[i] == null ? <Muted>—</Muted> : fmtScore(ci[i])}
                </Td>
              ))}
            </Tr>
          ) : null}
        </tbody>
      </DataTable>
    </div>
  );
}
