import type { ScorecardData } from "@/lib/contracts";
import { fmtScore, fmtValue, HUB_SIZE } from "@/lib/format";
import { PillarKey } from "./pillar";
import { DataTable, EvidenceTitle, Muted, Td, Th, Tr } from "./table";

export function ScorecardEvidence({ data }: { data: ScorecardData }) {
  return (
    <div className="space-y-4" data-testid="scorecard">
      <EvidenceTitle
        code={data.iata}
        title={data.name}
        sub={`${data.state} · ${HUB_SIZE[data.hub_size] ?? data.hub_size}`}
      />

      <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[13px]">
        <dt>Investment Opportunity Score</dt>
        <dd className="num text-right font-semibold">
          {data.score == null ? "Not ranked" : fmtScore(data.score)}
          {data.provisional && data.score != null ? (
            <span className="ml-1.5 text-[11px] font-medium text-[var(--warn)]">Provisional</span>
          ) : null}
        </dd>
        <dt className="text-[var(--ink-muted)]">National rank</dt>
        <dd className="num text-right">
          {data.national_rank ?? "—"} <Muted>of {data.national_of}</Muted>
        </dd>
        <dt className="text-[var(--ink-muted)]">Rank within {HUB_SIZE[data.hub_size]?.toLowerCase() ?? "hub size"}</dt>
        <dd className="num text-right">
          {data.hub_rank ?? "—"} <Muted>of {data.hub_of}</Muted>
        </dd>
      </dl>
      {data.not_ranked_reason ? (
        <p className="text-[12.5px] text-[var(--warn)]">Not ranked: {data.not_ranked_reason}</p>
      ) : null}

      <DataTable caption="Metrics by Pillar (percentile across Primary Airports)">
        <thead>
          <tr>
            <Th>Metric</Th>
            <Th num>Raw value</Th>
            <Th num>Pctl</Th>
            <Th num>Wt</Th>
          </tr>
        </thead>
        {data.pillars.map((p) => (
          <tbody key={p.pillar}>
            <Tr className="bg-[var(--tint)]">
              <Td className="font-medium">
                <PillarKey pillar={p.pillar} />
              </Td>
              <Td num />
              <Td num className="font-semibold">
                {fmtScore(p.score)}
              </Td>
              <Td num>{p.weight.toFixed(2)}</Td>
            </Tr>
            {p.metrics.map((m) => (
              <Tr key={m.metric}>
                <Td className="pl-4">
                  {m.label}
                  {m.imputed ? (
                    <span className="num ml-1.5 text-[10.5px] text-[var(--warn)]" title="Missing: assumed at the median (50)">
                      imputed
                    </span>
                  ) : null}
                </Td>
                <Td num>{m.imputed ? <Muted>missing</Muted> : fmtValue(m.raw_value, m.unit)}</Td>
                <Td num className={m.imputed ? "text-[var(--ink-muted)]" : undefined}>
                  {fmtScore(m.percentile)}
                </Td>
                <Td num className="text-[var(--ink-muted)]">
                  {m.weight_in_pillar.toFixed(2)}
                </Td>
              </Tr>
            ))}
          </tbody>
        ))}
      </DataTable>
      {data.imputed_metrics.length > 0 ? (
        <p className="text-[12.5px] text-[var(--ink-muted)]">
          Imputed at the median: <span className="num text-[var(--ink)]">{data.imputed_metrics.join(", ")}</span>
        </p>
      ) : null}
    </div>
  );
}
