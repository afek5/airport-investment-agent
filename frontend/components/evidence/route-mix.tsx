import type { RouteMixData, Share } from "@/lib/contracts";
import { fmtInt, fmtPct } from "@/lib/format";
import { DataTable, EvidenceTitle, Muted, Td, Th, Tr } from "./table";

function ShareRow({ label, share, strong }: { label: string; share: Share; strong?: boolean }) {
  return (
    <Tr>
      <Td className={strong ? "font-semibold" : undefined}>{label}</Td>
      <Td num className={strong ? "font-semibold" : undefined}>
        {fmtPct(share.share_pct)}
      </Td>
      <Td num>{fmtInt(share.long_haul)}</Td>
      <Td num>{fmtInt(share.total)}</Td>
    </Tr>
  );
}

export function RouteMixEvidence({ data }: { data: RouteMixData }) {
  return (
    <div className="space-y-4" data-testid="route-mix">
      <EvidenceTitle
        code={data.iata}
        title={`Long-haul share (≥ ${fmtInt(data.min_miles)} mi)`}
        sub={`${data.airport_name} · ${data.window}`}
      />
      <DataTable caption="Long-haul share by variant · departures unless noted">
        <thead>
          <tr>
            <Th>Variant</Th>
            <Th num>Share</Th>
            <Th num>Long-haul</Th>
            <Th num>Total</Th>
          </tr>
        </thead>
        <tbody>
          <ShareRow label="Passenger flights (F)" share={data.passenger_departures} strong />
          <ShareRow label="Passenger-weighted (pax)" share={data.passenger_weighted} />
          <ShareRow label="Cargo-inclusive (all)" share={data.cargo_inclusive_departures} />
          <ShareRow label="Non-passenger (G, L, P)" share={data.non_passenger_departures} />
          <ShareRow label="All-cargo (G, P)" share={data.all_cargo_departures} />
        </tbody>
      </DataTable>

      <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[12.5px]">
        <dt className="text-[var(--ink-muted)]">Non-passenger share of all departures</dt>
        <dd className="num text-right">{fmtPct(data.non_passenger_departure_share_pct)}</dd>
        <dt className="text-[var(--ink-muted)]">All-cargo share of long-haul departures</dt>
        <dd className="num text-right">{fmtPct(data.all_cargo_share_of_long_haul_pct)}</dd>
        <dt className="text-[var(--ink-muted)]">Non-passenger share of long-haul departures</dt>
        <dd className="num text-right">{fmtPct(data.non_passenger_share_of_long_haul_pct)}</dd>
      </dl>

      <DataTable caption="By service class">
        <thead>
          <tr>
            <Th>Class</Th>
            <Th num>Departures</Th>
            <Th num>Long-haul</Th>
            <Th num title="This class's long-haul departures / all long-haul departures">
              % of LH
            </Th>
          </tr>
        </thead>
        <tbody>
          {data.by_service_class.map((r) => (
            <Tr key={r.service_class}>
              <Td>
                <span className="num">{r.service_class}</span> <Muted>{r.label}</Muted>
              </Td>
              <Td num>{fmtInt(r.departures)}</Td>
              <Td num>{fmtInt(r.long_haul_departures)}</Td>
              <Td num>{fmtPct(r.share_of_long_haul_pct)}</Td>
            </Tr>
          ))}
        </tbody>
      </DataTable>

      {data.top_long_haul_destinations.length > 0 ? (
        <DataTable caption="Top long-haul destinations">
          <thead>
            <tr>
              <Th>Dest</Th>
              <Th num>Miles</Th>
              <Th num>Departures</Th>
              <Th num>Passengers</Th>
            </tr>
          </thead>
          <tbody>
            {data.top_long_haul_destinations.map((d) => (
              <Tr key={d.dest}>
                <Td className="num">
                  {d.dest}
                  {d.dest_country && d.dest_country !== "US" ? <Muted> {d.dest_country}</Muted> : null}
                </Td>
                <Td num>{fmtInt(d.distance_mi)}</Td>
                <Td num>{fmtInt(d.departures)}</Td>
                <Td num>{fmtInt(d.passengers)}</Td>
              </Tr>
            ))}
          </tbody>
        </DataTable>
      ) : null}
    </div>
  );
}
