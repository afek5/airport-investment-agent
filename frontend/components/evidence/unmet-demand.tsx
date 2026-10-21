import type { UnmetDemandData } from "@/lib/contracts";
import { fmtInt, fmtPct, fmtSigned, fmtValue } from "@/lib/format";
import { Chip } from "./evidence-meta";
import { Block, DataTable, EvidenceTitle, Td, Th, Tr } from "./table";

/** "BTS TranStats T-100 Segment (All Carriers), …" → "BTS TranStats T-100 Segment"; the full text stays in the tooltip. */
function shortSource(source: string): string {
  const s = source.split(/[:,(]/)[0].trim();
  return s.length > 48 ? `${s.slice(0, 47)}…` : s;
}

function benchCaption(data: UnmetDemandData): string {
  const labels = [...new Set(data.constraint_evidence.map((e) => e.benchmark_label).filter(Boolean))];
  return labels.length === 1 ? `Median = ${labels[0]}` : "Value vs benchmark";
}

/** Unmet Demand: Observed evidence, Forecast gap and Scenario as three labelled blocks, then what the data can't tell us. */
export function UnmetDemandEvidence({ data }: { data: UnmetDemandData }) {
  const fg = data.forecast_gap;
  const sc = data.spill_scenario;
  return (
    <div className="space-y-4" data-testid="unmet-demand">
      <EvidenceTitle code={data.iata} title="Unmet Demand" sub={data.name} />

      <Block label="Observed evidence" tag={<Chip>observed</Chip>} testId="block-observed">
        {data.constraint_evidence.length === 0 ? (
          <p className="text-[13px] text-[var(--ink-muted)]">No Constraint Evidence available for this airport.</p>
        ) : (
          <DataTable caption={benchCaption(data)}>
            <thead>
              <tr>
                <Th>Signal</Th>
                <Th num>Value</Th>
                <Th num>Median</Th>
              </tr>
            </thead>
            <tbody>
              {data.constraint_evidence.map((e) => (
                <Tr key={e.key}>
                  <Td>
                    {e.label}
                    <div className="line-clamp-1 text-[11px] text-[var(--ink-muted)]" title={e.source}>
                      {shortSource(e.source)} · {e.as_of}
                    </div>
                  </Td>
                  <Td num className="font-medium">
                    {fmtValue(e.value, e.unit)}
                  </Td>
                  <Td num className="text-[var(--ink-muted)]">
                    {e.benchmark != null ? fmtValue(e.benchmark, e.unit) : "—"}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </DataTable>
        )}
        {data.why_drivers.length > 0 ? (
          <div>
            <h5 className="mb-1 text-[12px] font-medium text-[var(--ink-muted)]">Why, strongest driver first</h5>
            <ol className="list-decimal space-y-0.5 pl-5 text-[13px] marker:text-[var(--ink-muted)]">
              {data.why_drivers.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ol>
          </div>
        ) : null}
      </Block>

      <Block label="Forecast gap" tag={<Chip>FAA TAF forecast</Chip>} testId="block-forecast">
        {fg ? (
          <DataTable>
            <thead>
              <tr>
                <Th />
                <Th num>Enplanements</Th>
                {fg.ops_from != null ? <Th num>Air-carrier ops</Th> : null}
              </tr>
            </thead>
            <tbody>
              <Tr>
                <Td className="num">FY{fg.from_fy}</Td>
                <Td num>{fmtInt(fg.enplanements_from)}</Td>
                {fg.ops_from != null ? <Td num>{fmtInt(fg.ops_from)}</Td> : null}
              </Tr>
              <Tr>
                <Td className="num">FY{fg.to_fy}</Td>
                <Td num>{fmtInt(fg.enplanements_to)}</Td>
                {fg.ops_from != null ? <Td num>{fmtInt(fg.ops_to)}</Td> : null}
              </Tr>
              <Tr>
                <Td>Change</Td>
                <Td num className="font-medium">
                  {fmtSigned(fg.enplanements_abs, fmtInt)}
                  <div className="text-[11px] font-normal text-[var(--ink-muted)]">{fmtSigned(fg.enplanements_pct, (v) => fmtPct(v))}</div>
                </Td>
                {fg.ops_from != null ? (
                  <Td num className="font-medium">
                    {fmtSigned(fg.ops_abs, fmtInt)}
                    <div className="text-[11px] font-normal text-[var(--ink-muted)]">{fmtSigned(fg.ops_pct, (v) => fmtPct(v))}</div>
                  </Td>
                ) : null}
              </Tr>
            </tbody>
          </DataTable>
        ) : (
          <p className="text-[13px] text-[var(--ink-muted)]">No FAA forecast available for this airport.</p>
        )}
      </Block>

      <Block label="Scenario" tag={<Chip tone="warn">not observed · not calibrated</Chip>} testId="block-scenario">
        {sc ? (
          <div className="space-y-2.5">
            <p className="text-[12.5px] font-medium">{sc.label}</p>
            <p className="text-[13px]">
              Spill Scenario range:{" "}
              <span className="num font-semibold">
                {fmtInt(sc.low)}–{fmtInt(sc.high)}
              </span>{" "}
              passengers
            </p>
            {sc.parameters.length > 0 ? (
              <ul className="list-disc space-y-0.5 pl-5 text-[12.5px] text-[var(--ink-muted)]">
                {sc.parameters.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : null}
            {sc.top_routes.length > 0 ? (
              <DataTable caption="Top routes in the scenario">
                <thead>
                  <tr>
                    <Th>Dest</Th>
                    <Th num title="Route-months over the load-factor threshold">
                      Months
                    </Th>
                    <Th num>Low–high</Th>
                  </tr>
                </thead>
                <tbody>
                  {sc.top_routes.map((r) => (
                    <Tr key={r.dest}>
                      <Td className="num">{r.dest}</Td>
                      <Td num>{r.months_over_threshold}</Td>
                      <Td num>
                        {fmtInt(r.low)}–{fmtInt(r.high)}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </DataTable>
            ) : null}
          </div>
        ) : (
          <p className="text-[13px] text-[var(--ink-muted)]">No route-months above the load-factor threshold, so no scenario.</p>
        )}
      </Block>

      <Block label="What the data can't tell us" testId="block-cannot">
        <ul className="list-disc space-y-0.5 pl-5 text-[13px]">
          {data.cannot_determine.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Block>
    </div>
  );
}
