"""route_mix: the Long-haul share of an airport's departures (SPEC §4 "Long-haul")."""

from __future__ import annotations

from app.analytics.constants import (
    ALL_CARGO_CLASSES, CARGO_HEAVY_SHARE_PCT, LONG_HAUL_MILES, PASSENGER_CLASS, SERVICE_CLASS_LABELS,
    T100_SOURCE_NAME, T100_URL, TOP_DESTINATIONS,
)
from app.contracts import (
    DataConfidence, LongHaulDestination, RouteMixData, ServiceClassRow, Share, Source, ToolResult,
)
from app.snapshot import get_conn

WINDOW_MONTHS = 12
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def pct(part: float, total: float) -> float:
    return round(100.0 * part / total, 1) if total else 0.0


def last_months(conn, n: int = WINDOW_MONTHS) -> list[tuple[int, int]]:
    rows = conn.execute(
        "SELECT DISTINCT year, month FROM t100_routes ORDER BY year DESC, month DESC LIMIT ?", [n]
    ).fetchall()
    return sorted((int(y), int(m)) for y, m in rows)


def window_label(months: list[tuple[int, int]]) -> str:
    (y0, m0), (y1, m1) = months[0], months[-1]
    return f"{len(months)} months, {_MON[m0 - 1]} {y0}–{_MON[m1 - 1]} {y1}"


def route_mix(iata: str, min_miles: int = LONG_HAUL_MILES, include_cargo: bool = False) -> ToolResult[RouteMixData]:
    """Long-haul share of departures from `iata` over the last 12 T-100 months."""
    iata = iata.strip().upper()
    conn = get_conn()
    name_row = conn.execute("SELECT name FROM airports WHERE iata = ?", [iata]).fetchone()
    months = last_months(conn)
    if not months:
        raise ValueError("t100_routes is empty")
    keys = [y * 100 + m for y, m in months]
    in_window = f"(year * 100 + month) IN ({','.join('?' * len(keys))})"

    by_class = conn.execute(
        f"""SELECT service_class,
                   SUM(departures_performed),
                   SUM(CASE WHEN distance_mi >= ? THEN departures_performed ELSE 0 END),
                   SUM(passengers),
                   SUM(CASE WHEN distance_mi >= ? THEN passengers ELSE 0 END),
                   SUM(freight_lbs)
            FROM t100_routes WHERE origin = ? AND {in_window}
            GROUP BY service_class ORDER BY service_class""",
        [min_miles, min_miles, iata, *keys],
    ).fetchall()
    if not by_class:
        raise ValueError(f"No T-100 departures from {iata} in the Snapshot window")

    cls = {r[0]: [int(v or 0) for v in r[1:]] for r in by_class}
    f = cls.get(PASSENGER_CLASS, [0, 0, 0, 0, 0])
    all_deps = sum(v[0] for v in cls.values())
    all_lh = sum(v[1] for v in cls.values())
    # Pre-computed group aggregates, so the agent never has to add rows together (SPEC §6).
    non_pax = [c for c in cls if c != PASSENGER_CLASS]
    cargo = [c for c in cls if c in ALL_CARGO_CLASSES]

    def group_share(classes: list[str]) -> Share:
        deps = sum(cls[c][0] for c in classes)
        lh = sum(cls[c][1] for c in classes)
        return Share(long_haul=lh, total=deps, share_pct=pct(lh, deps))

    non_pax_share_obj = group_share(non_pax)
    cargo_share_obj = group_share(cargo)

    dest_classes = list(cls) if include_cargo else [PASSENGER_CLASS]
    dests = conn.execute(
        f"""SELECT dest, any_value(dest_country), MAX(distance_mi), SUM(departures_performed), SUM(passengers)
            FROM t100_routes
            WHERE origin = ? AND distance_mi >= ? AND service_class IN ({','.join('?' * len(dest_classes))})
              AND {in_window}
            GROUP BY dest ORDER BY 4 DESC, dest LIMIT ?""",
        [iata, min_miles, *dest_classes, *keys, TOP_DESTINATIONS],
    ).fetchall()

    window = window_label(months)
    non_pax_share = pct(all_deps - f[0], all_deps)
    data = RouteMixData(
        iata=iata,
        airport_name=name_row[0] if name_row else iata,
        min_miles=min_miles,
        include_cargo=include_cargo,
        window=window,
        months=[f"{y}-{m:02d}" for y, m in months],
        passenger_departures=Share(long_haul=f[1], total=f[0], share_pct=pct(f[1], f[0])),
        passenger_weighted=Share(long_haul=f[3], total=f[2], share_pct=pct(f[3], f[2])),
        cargo_inclusive_departures=Share(long_haul=all_lh, total=all_deps, share_pct=pct(all_lh, all_deps)),
        non_passenger_departure_share_pct=non_pax_share,
        non_passenger_departures=non_pax_share_obj,
        all_cargo_departures=cargo_share_obj,
        all_cargo_share_of_long_haul_pct=pct(cargo_share_obj.long_haul, all_lh),
        non_passenger_share_of_long_haul_pct=pct(non_pax_share_obj.long_haul, all_lh),
        by_service_class=[
            ServiceClassRow(service_class=c, label=SERVICE_CLASS_LABELS.get(c, "other"), departures=v[0],
                            long_haul_departures=v[1], passengers=v[2], freight_lbs=v[4],
                            share_of_departures_pct=pct(v[0], all_deps),
                            long_haul_share_pct=pct(v[1], v[0]),
                            share_of_long_haul_pct=pct(v[1], all_lh))
            for c, v in cls.items()
        ],
        top_long_haul_destinations=[
            LongHaulDestination(dest=d, dest_country=c, distance_mi=int(dist), departures=int(n), passengers=int(p or 0))
            for d, c, dist, n, p in dests
        ],
    )

    dest_scope = "all service classes" if include_cargo else "scheduled passenger flights (class F) only"
    assumptions = [
        f"Long-haul Flight = a flight segment of {min_miles:,} statute miles or more (T-100 segment distance).",
        f"Headline share counts scheduled passenger flights (class F), departures performed from {iata}.",
        "Passenger-weighted share = passengers on long-haul segments / all class F passengers.",
        "Cargo-inclusive share counts every T-100 service class (F, G, L, P): a separately labelled variant.",
        "Non-passenger = classes G, L and P; all-cargo = classes G and P (L charters can carry passengers).",
        "Zero-departure T-100 rows are dropped; carriers and aircraft types are aggregated.",
        f"Top long-haul destinations list {dest_scope}.",
    ]
    caveats = ["T-100 reports flight segments: a multi-stop flight counts each leg separately."]
    if non_pax_share > CARGO_HEAVY_SHARE_PCT:
        caveats.append(
            f"{iata} is cargo-heavy: {non_pax_share}% of all departures are not scheduled passenger flights, "
            f"and all-cargo flights (classes G + P) make {cargo_share_obj.long_haul:,} of the "
            f"{all_lh:,} long-haul departures ({data.all_cargo_share_of_long_haul_pct}%), "
            f"so the cargo-inclusive share ({data.cargo_inclusive_departures.share_pct}%) differs strongly "
            f"from the passenger share ({data.passenger_departures.share_pct}%)."
        )
    level = "High" if len(months) >= WINDOW_MONTHS else "Medium"
    reasons = [f"T-100 is a census of all carriers' segments; {window}."]
    if len(months) < WINDOW_MONTHS:
        reasons.append(f"only {len(months)} of {WINDOW_MONTHS} months available; not an annual figure")
    return ToolResult[RouteMixData](
        data=data,
        sources=[Source(name=T100_SOURCE_NAME, url=T100_URL, as_of=window.split("–")[-1], window=window)],
        assumptions=assumptions,
        data_confidence=DataConfidence(level=level, reasons=reasons),
        caveats=caveats,
    )
