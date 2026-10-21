import type { RankingData } from "@/lib/contracts";
import { fmtScore, HUB_SIZE } from "@/lib/format";
import { PillarKey } from "./pillar";
import { DataTable, EvidenceTitle, Muted, Td, Th, Tr } from "./table";

const PILLAR_LABEL = { overall: "Investment Opportunity Score", momentum: "Demand Momentum", pressure: "Capacity Pressure", scale: "Market Scale" };

function weightsLine(w: RankingData["weights"]) {
  return `Weights: Momentum ${w.momentum.toFixed(2)} · Pressure ${w.pressure.toFixed(2)} · Scale ${w.scale.toFixed(2)}`;
}

export function RankingEvidence({ data }: { data: RankingData }) {
  const provisional = data.ranked.filter((r) => r.provisional);
  return (
    <div className="space-y-4" data-testid="ranking">
      <EvidenceTitle
        title={`Ranking · ${data.scope}`}
        sub={
          <>
            {PILLAR_LABEL[data.pillar] ?? data.pillar} · {weightsLine(data.weights)} · universe {data.universe_size} Primary Airports
          </>
        }
      />
      <DataTable caption={`Top ${data.ranked.length} by ${data.pillar === "overall" ? "score" : PILLAR_LABEL[data.pillar]} · Pillar scores M / P / S`}>
        <thead>
          <tr>
            <Th num className="pr-2">#</Th>
            <Th className="pr-2">Airport</Th>
            <Th num className="pr-2" title="Investment Opportunity Score, with Coverage (measured metrics of 7)">
              Score
            </Th>
            <Th num className="pr-2">
              <PillarKey pillar="momentum" letter />
            </Th>
            <Th num className="pr-2">
              <PillarKey pillar="pressure" letter />
            </Th>
            <Th num>
              <PillarKey pillar="scale" letter />
            </Th>
          </tr>
        </thead>
        <tbody>
          {data.ranked.map((r) => (
            <Tr key={r.iata}>
              <Td num className="pr-2 text-[var(--ink-muted)]">
                {r.rank}
              </Td>
              <Td className="max-w-[8rem] pr-2">
                <div className="truncate" title={r.name}>
                  <span className="num font-medium">{r.iata}</span> {r.name}
                </div>
                <div className="truncate text-[11.5px] text-[var(--ink-muted)]">
                  {r.state} · {HUB_SIZE[r.hub_size] ?? r.hub_size}
                </div>
              </Td>
              <Td num className="pr-2">
                <span className="font-semibold">{fmtScore(r.score)}</span>
                {r.provisional ? (
                  <sup className="ml-0.5 text-[10px] font-medium text-[var(--warn)]" title="Provisional Score">
                    P
                  </sup>
                ) : null}
                <div
                  className={r.coverage.measured < r.coverage.of ? "text-[11px] text-[var(--warn)]" : "text-[11px] text-[var(--ink-muted)]"}
                  title="Coverage: measured metrics"
                >
                  {r.coverage.measured}/{r.coverage.of}
                </div>
              </Td>
              <Td num className="pr-2">{fmtScore(r.pillars.momentum)}</Td>
              <Td num className="pr-2">{fmtScore(r.pillars.pressure)}</Td>
              <Td num>{fmtScore(r.pillars.scale)}</Td>
            </Tr>
          ))}
        </tbody>
      </DataTable>

      {provisional.length > 0 ? (
        <div className="text-[12.5px] leading-[1.5]" data-testid="provisional-list">
          <p className="mb-1">
            <span className="num font-medium text-[var(--warn)]">P</span> Provisional Score: missing metrics are assumed
            at the median (50th percentile).
          </p>
          <ul className="space-y-0.5 text-[var(--ink-muted)]">
            {provisional.map((r) => (
              <li key={r.iata}>
                <span className="num text-[var(--ink)]">{r.iata}</span> {r.coverage.measured}/{r.coverage.of} · imputed:{" "}
                <span className="num">{r.imputed_metrics.join(", ") || "—"}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {data.not_ranked.length > 0 ? (
        <div className="text-[12.5px]" data-testid="not-ranked">
          <h4 className="eyebrow mb-1">Not ranked: insufficient data</h4>
          <ul className="space-y-0.5">
            {data.not_ranked.map((n) => (
              <li key={n.iata}>
                <span className="num">{n.iata}</span> {n.name} <Muted>· {n.reason}</Muted>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
