import type { LiveDelaysData, LiveTrafficData, OdDemandData } from "@/lib/contracts";
import { fmtInt, fmtMonth, fmtNum, fmtPct } from "@/lib/format";
import { DataTable, EvidenceTitle, Muted, Td, Th, Tr } from "./table";

export function LiveTrafficEvidence({ data }: { data: LiveTrafficData }) {
  return (
    <div className="space-y-4" data-testid="live-traffic">
      <EvidenceTitle code={data.iata} title="Monthly traffic" sub="BTS monthly airport data, fetched live" />
      {data.months.length === 0 ? (
        <p className="text-[13px] text-[var(--ink-muted)]">The live source returned no months for this airport.</p>
      ) : (
        <DataTable>
          <thead>
            <tr>
              <Th>Month</Th>
              <Th num>Deps</Th>
              <Th num>Passengers</Th>
              <Th num>Seats</Th>
              <Th num>LF</Th>
            </tr>
          </thead>
          <tbody>
            {data.months.map((m) => (
              <Tr key={`${m.year}-${m.month}`}>
                <Td className="num whitespace-nowrap">{fmtMonth(m.year, m.month)}</Td>
                <Td num>{fmtInt(m.departures)}</Td>
                <Td num>{fmtInt(m.passengers)}</Td>
                <Td num>{fmtInt(m.seats)}</Td>
                <Td num>{fmtPct(m.load_factor_pct)}</Td>
              </Tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </div>
  );
}

export function OdDemandEvidence({ data }: { data: OdDemandData }) {
  const period = data.year ? `Q${data.quarter ?? "?"} ${data.year}` : "latest quarter";
  return (
    <div className="space-y-4" data-testid="od-demand">
      <EvidenceTitle code={data.iata} title="O&D demand" sub={`DOT Airline Fare Report · ${period}`} />
      {data.markets.length === 0 ? (
        <p className="text-[13px] text-[var(--ink-muted)]">The live source returned no markets for this airport.</p>
      ) : (
        <DataTable>
          <thead>
            <tr>
              <Th>Market</Th>
              <Th num>Pax/day</Th>
              <Th num>Fare</Th>
              <Th>Largest carrier</Th>
            </tr>
          </thead>
          <tbody>
            {data.markets.map((m) => (
              <Tr key={m.other_airport}>
                <Td>
                  <span className="num">{m.other_airport}</span>
                  {m.other_city ? <div className="text-[11.5px] text-[var(--ink-muted)]">{m.other_city}</div> : null}
                </Td>
                <Td num>{fmtNum(m.passengers_per_day)}</Td>
                <Td num>{m.fare == null ? "—" : `$${fmtNum(m.fare)}`}</Td>
                <Td>
                  {m.carrier_lg ? (
                    <>
                      <span className="num">{m.carrier_lg}</span>{" "}
                      {m.large_ms_pct != null ? <Muted>{fmtPct(m.large_ms_pct)}</Muted> : null}
                    </>
                  ) : (
                    <Muted>—</Muted>
                  )}
                </Td>
              </Tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </div>
  );
}

export function LiveDelaysEvidence({ data }: { data: LiveDelaysData }) {
  return (
    <div className="space-y-3" data-testid="live-delays">
      <EvidenceTitle
        title="Live NAS status"
        sub={`FAA NAS Status${data.update_time ? ` · updated ${data.update_time}` : ""} · queried ${data.queried.join(", ") || "all"}`}
      />
      {data.delays.length > 0 ? (
        <DataTable>
          <thead>
            <tr>
              <Th>Airport</Th>
              <Th>Program</Th>
              <Th>Delay</Th>
            </tr>
          </thead>
          <tbody>
            {data.delays.map((d, i) => (
              <Tr key={`${d.iata}-${d.kind}-${i}`}>
                <Td className="num">{d.iata}</Td>
                <Td>
                  {d.kind}
                  {d.reason ? <div className="text-[11.5px] text-[var(--ink-muted)]">{d.reason}</div> : null}
                </Td>
                <Td className="num whitespace-nowrap">
                  {[d.min_delay, d.max_delay].filter(Boolean).join("–") || (d.avg_delay ? `avg ${d.avg_delay}` : "—")}
                  {d.trend ? <div className="text-[11px] text-[var(--ink-muted)]">{d.trend}</div> : null}
                  {d.until ? <div className="text-[11px] text-[var(--ink-muted)]">until {d.until}</div> : null}
                </Td>
              </Tr>
            ))}
          </tbody>
        </DataTable>
      ) : null}
      {data.no_active_delay.length > 0 ? (
        <p className="text-[13px]">
          <span className="text-[var(--ok)]">No active delay</span> at{" "}
          <span className="num">{data.no_active_delay.join(", ")}</span>
        </p>
      ) : null}
    </div>
  );
}
