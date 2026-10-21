import type { RouteMixData, Share } from "@/lib/contracts";

const fmt = (n: number) => n.toLocaleString("en-US");

function ShareRow({ label, share, unit }: { label: string; share: Share; unit: string }) {
  return (
    <tr className="border-t border-[var(--hairline)]">
      <td className="py-1.5 pr-3">{label}</td>
      <td className="num py-1.5 pr-3 text-right">{share.share_pct.toFixed(1)}%</td>
      <td className="num py-1.5 pr-3 text-right">{fmt(share.long_haul)}</td>
      <td className="num py-1.5 text-right">
        {fmt(share.total)} <span className="text-[var(--ink-muted)]">{unit}</span>
      </td>
    </tr>
  );
}

const th = "num py-1.5 text-xs font-medium uppercase tracking-[0.06em] text-[var(--ink-muted)]";

export function RouteMixEvidence({ data }: { data: RouteMixData }) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-[15px] font-semibold">
          <span className="num">{data.iata}</span> · Long-haul share (≥ {fmt(data.min_miles)} mi)
        </h3>
        <p className="text-xs text-[var(--ink-muted)]">
          {data.airport_name} · {data.window}
        </p>
      </div>
      <table className="w-full text-[13px]">
        <thead>
          <tr>
            <th className={`${th} text-left`}>Variant</th>
            <th className={`${th} text-right`}>Share</th>
            <th className={`${th} text-right`}>Long-haul</th>
            <th className={`${th} text-right`}>Total</th>
          </tr>
        </thead>
        <tbody>
          <ShareRow label="Passenger flights (class F)" share={data.passenger_departures} unit="deps" />
          <ShareRow label="Passenger-weighted" share={data.passenger_weighted} unit="pax" />
          <ShareRow label="Cargo-inclusive (all classes)" share={data.cargo_inclusive_departures} unit="deps" />
          <ShareRow label="Non-passenger (G, L, P)" share={data.non_passenger_departures} unit="deps" />
          <ShareRow label="All-cargo (G, P)" share={data.all_cargo_departures} unit="deps" />
        </tbody>
      </table>

      <table className="w-full text-[13px]">
        <caption className={`${th} text-left`}>By service class</caption>
        <thead>
          <tr>
            <th className={`${th} text-left`}>Class</th>
            <th className={`${th} text-right`}>Departures</th>
            <th className={`${th} text-right`}>Long-haul</th>
            <th className={`${th} text-right`}>% of long-haul</th>
          </tr>
        </thead>
        <tbody>
          {data.by_service_class.map((r) => (
            <tr key={r.service_class} className="border-t border-[var(--hairline)]">
              <td className="py-1.5 pr-3">
                <span className="num">{r.service_class}</span> {r.label}
              </td>
              <td className="num py-1.5 pr-3 text-right">{fmt(r.departures)}</td>
              <td className="num py-1.5 pr-3 text-right">{fmt(r.long_haul_departures)}</td>
              <td className="num py-1.5 text-right">{r.share_of_long_haul_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.top_long_haul_destinations.length > 0 && (
        <table className="w-full text-[13px]">
          <caption className={`${th} text-left`}>Top long-haul destinations</caption>
          <thead>
            <tr>
              <th className={`${th} text-left`}>Dest</th>
              <th className={`${th} text-right`}>Miles</th>
              <th className={`${th} text-right`}>Departures</th>
              <th className={`${th} text-right`}>Passengers</th>
            </tr>
          </thead>
          <tbody>
            {data.top_long_haul_destinations.map((d) => (
              <tr key={d.dest} className="border-t border-[var(--hairline)]">
                <td className="num py-1.5 pr-3">
                  {d.dest}
                  {d.dest_country && d.dest_country !== "US" ? (
                    <span className="text-[var(--ink-muted)]"> {d.dest_country}</span>
                  ) : null}
                </td>
                <td className="num py-1.5 pr-3 text-right">{fmt(d.distance_mi)}</td>
                <td className="num py-1.5 pr-3 text-right">{fmt(d.departures)}</td>
                <td className="num py-1.5 text-right">{fmt(d.passengers)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
