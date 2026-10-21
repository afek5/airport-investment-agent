import type { AdHocData, PublicApiData, ResolveData } from "@/lib/contracts";
import { fmtNum, HUB_SIZE } from "@/lib/format";
import { DataTable, EvidenceTitle, Muted, Td, Th, Tr } from "./table";

// Period labels read as written ("2026", not "2,026").
const PERIOD_COL = /^(year|quarter|month|fiscal_year)$/;

function cell(v: unknown, column: string): React.ReactNode {
  if (v == null) return <Muted>—</Muted>;
  if (typeof v === "number") return PERIOD_COL.test(column) ? String(v) : fmtNum(v);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

const isPublicApi = (d: AdHocData): d is PublicApiData => "dataset" in d && "resource_id" in d;

/** Ad-hoc rows: query_snapshot (Snapshot SQL) and query_public_api (live SoQL on a whitelisted dataset). */
export function AdHocEvidence({ data }: { data: AdHocData | PublicApiData }) {
  const numericCols = data.columns.map((c, ci) => !PERIOD_COL.test(c) && data.rows.some((r) => typeof r[ci] === "number"));
  const api = isPublicApi(data) ? data : null;
  const cap = api ? `the ${api.limit}-row limit` : "the 200-row cap";
  return (
    <div className="space-y-3" data-testid="ad-hoc">
      <EvidenceTitle
        title={
          api ? (
            <>
              Ad-hoc live query · <span className="num">{api.dataset}</span>
            </>
          ) : (
            "Ad-hoc Snapshot query"
          )
        }
        sub={`${api ? `${api.resource_id} · ` : ""}${data.row_count} row${data.row_count === 1 ? "" : "s"}${data.truncated ? ` · truncated at ${cap}` : ""}`}
      />
      <pre className="num overflow-x-auto whitespace-pre-wrap break-words rounded-[10px] bg-[var(--tint)] p-3 text-[12px] leading-[1.5]">
        {data.sql}
      </pre>
      {data.rows.length > 0 ? (
        <DataTable>
          <thead>
            <tr>
              {data.columns.map((c, i) => (
                <Th key={c} num={numericCols[i]}>
                  {c}
                </Th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.slice(0, 50).map((r, ri) => (
              <Tr key={ri}>
                {r.map((v, ci) => (
                  <Td key={ci} num={numericCols[ci]} className={numericCols[ci] ? undefined : "num"}>
                    {cell(v, data.columns[ci])}
                  </Td>
                ))}
              </Tr>
            ))}
          </tbody>
        </DataTable>
      ) : (
        <p className="text-[13px] text-[var(--ink-muted)]">The query returned no rows.</p>
      )}
      {data.rows.length > 50 ? (
        <p className="text-xs text-[var(--ink-muted)]">Showing the first 50 of {data.rows.length} rows returned.</p>
      ) : null}
    </div>
  );
}

export function ResolveEvidence({ data }: { data: ResolveData }) {
  return (
    <div className="space-y-3" data-testid="resolve">
      <EvidenceTitle
        title={
          <>
            “{data.query}” → <span className="num">{data.resolved ?? "no match"}</span>
          </>
        }
        sub={data.alternates.length > 0 ? `Alternates: ${data.alternates.join(", ")}` : "Airport resolution"}
      />
      {data.candidates.length > 0 ? (
        <DataTable>
          <thead>
            <tr>
              <Th>Code</Th>
              <Th>Airport</Th>
              <Th>Hub size</Th>
            </tr>
          </thead>
          <tbody>
            {data.candidates.map((c) => (
              <Tr key={c.iata} className={c.iata === data.resolved ? "bg-[var(--tint)]" : undefined}>
                <Td className="num font-medium">{c.iata}</Td>
                <Td>
                  {c.name}
                  <div className="text-[11.5px] text-[var(--ink-muted)]">
                    {c.city}, {c.state}
                  </div>
                </Td>
                <Td className="whitespace-nowrap text-[var(--ink-muted)]">{HUB_SIZE[c.hub_size] ?? c.hub_size}</Td>
              </Tr>
            ))}
          </tbody>
        </DataTable>
      ) : null}
    </div>
  );
}
