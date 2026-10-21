"""unmet_demand: observed Constraint Evidence first, the Forecast Gap, a separately labelled
Spill Scenario, and what the data cannot determine (SPEC §4 "Unmet Demand")."""

from __future__ import annotations

import pandas as pd

from app.analytics.common import has_table, in_months, is_missing, r1, table_source
from app.analytics.compare import derived_columns
from app.analytics.constants import (
    CANNOT_DETERMINE,
    DRIVER_MIN_STRENGTH,
    DRIVER_REQUIRES_POSITIVE,
    HIGH_LF,
    IFR_DROP_STRENGTH_PER_PCT,
    ONTIME_SCOPE_CAVEAT,
    PASSENGER_CLASS,
    SPILL_BUCKETS,
    SPILL_LABEL,
    SPILL_TOP_ROUTES,
    TAF_BASE_FY,
    TAF_GAP_FY,
)
from app.analytics.metrics import load_metrics
from app.analytics.scoring import percentile
from app.contracts import (
    DataConfidence,
    EvidenceItem,
    ForecastGap,
    SpillRoute,
    SpillScenario,
    ToolResult,
    UnmetDemandData,
)
from app.snapshot import get_conn


def spill_rates(lf: float) -> tuple[float, float] | None:
    """Assumed (low, high) spill rate for a route-month Load Factor (0–1); None at or below 0.85."""
    for lo, hi, r_lo, r_hi in SPILL_BUCKETS:
        if lo < lf <= hi:
            return r_lo, r_hi
    return None


def route_months(conn, months: list[tuple[int, int]], origin: str | None = None) -> pd.DataFrame:
    """Class F route-months (origin × dest × month) with passengers, seats and Load Factor (0–1)."""
    pred, keys = in_months(months)
    where = f"service_class = ? AND {pred}" + (" AND origin = ?" if origin else "")
    params = [PASSENGER_CLASS, *keys] + ([origin] if origin else [])
    df = conn.execute(f"""
        SELECT origin, dest, year, month, SUM(passengers) AS passengers, SUM(seats) AS seats
        FROM t100_routes WHERE {where} GROUP BY origin, dest, year, month HAVING SUM(seats) > 0""", params).df()
    df["lf"] = df["passengers"] / df["seats"]
    return df


def spill_scenario(rm: pd.DataFrame) -> SpillScenario:
    rows = []
    for r in rm.itertuples(index=False):
        rates = spill_rates(float(r.lf))
        if rates:
            rows.append((r.dest, float(r.passengers) * rates[0], float(r.passengers) * rates[1]))
    by_dest: dict[str, list[float]] = {}
    for dest, lo, hi in rows:
        acc = by_dest.setdefault(dest, [0, 0.0, 0.0])
        acc[0] += 1
        acc[1] += lo
        acc[2] += hi
    top = sorted(by_dest.items(), key=lambda kv: (-kv[1][2], kv[0]))[:SPILL_TOP_ROUTES]
    params = [f"Load Factor {lo:.2f}–{hi:.2f}: assumed spill {r_lo:.0%}–{r_hi:.0%} of carried passengers"
              if hi != float("inf") else f"Load Factor above {lo:.2f}: assumed spill {r_lo:.0%}–{r_hi:.0%} of "
              "carried passengers" for lo, hi, r_lo, r_hi in SPILL_BUCKETS]
    params += [f"Only class F route-months with Load Factor above {HIGH_LF:.2f} contribute.",
               "Spill rates are illustrative assumptions, not calibrated to this airport or any booking data."]
    return SpillScenario(
        label=SPILL_LABEL,
        low=float(round(sum(r[1] for r in rows))), high=float(round(sum(r[2] for r in rows))),
        parameters=params,
        top_routes=[SpillRoute(dest=d, months_over_threshold=int(v[0]), low=float(round(v[1])),
                               high=float(round(v[2]))) for d, v in top],
    )


def _median(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.median()) if len(s) else None


def unmet_demand(iata: str) -> ToolResult[UnmetDemandData]:
    """Unmet Demand at one airport, argued from observed Constraint Evidence and the FAA Forecast Gap,
    with a separately labelled Spill Scenario and the fixed list of what the data cannot determine."""
    code = iata.strip().upper()
    conn = get_conn()
    mf = load_metrics(conn)
    if code not in mf.df.index:
        raise ValueError(f"{code} is not a Primary Airport in the Snapshot; use resolve_airports first")
    df = derived_columns(mf)
    t100_asof = mf.t100_window.split("–")[-1]
    ontime_asof = mf.ontime_window.split("–")[-1]
    t100_src = table_source("t100_routes", window=mf.t100_window, as_of=t100_asof)
    ontime_src = table_source("ontime_airport_month", window=mf.ontime_window, as_of=ontime_asof)
    evidence: list[EvidenceItem] = []
    assumptions = [
        "Constraint Evidence is observed data; benchmarks are national medians of FAA Primary Airports.",
        ("Driver strength = the airport's national percentile on that indicator (IFR drop: 2 points per "
         "percentage point of arrival-rate loss, capped at 100); indicators above the median become "
         "why-drivers (passenger-minus-seat growth only when positive)."),
        "Current NAS status is a Live Signal from the live_delays tool, not part of this Snapshot evidence.",
    ]
    caveats = [ONTIME_SCOPE_CAVEAT]

    def national(key: str, label: str, unit: str, source: str, as_of: str, strength: bool = True) -> None:
        col = df[key].astype("float64")
        v = col[code]
        evidence.append(EvidenceItem(
            key=key, label=label, value=r1(v), unit=unit, benchmark=r1(_median(col)),
            benchmark_label="national median, Primary Airports", source=source, as_of=as_of,
            strength=r1(percentile(col)[code]) if strength and not is_missing(v) else None))

    ontime_name = ontime_src.name if ontime_src else "BTS Reporting Carrier On-Time Performance"
    t100_name = t100_src.name if t100_src else "BTS T-100 Segment (All Carriers)"
    national("delay_share", "Departures delayed ≥15 min", "%", ontime_name, ontime_asof)
    national("taxi_out", "Average taxi-out", "min", ontime_name, ontime_asof)
    national("nas_delay_min_per_flight", "NAS (airspace/airport) delay per departure", "min", ontime_name,
             ontime_asof)

    # Runway capacity: IFR vs VFR arrival-rate drop (hand-coded table, only some airports).
    cap = None
    if has_table(conn, "runway_capacity"):
        cur = conn.execute("SELECT * FROM runway_capacity WHERE iata = ?", [code])
        row = cur.fetchone()
        rec = dict(zip([d[0] for d in cur.description], row)) if row else {}
        cap = (rec.get("vfr_arrivals_hr"), rec.get("ifr_arrivals_hr"), rec.get("source_note"),
               rec.get("profile_year")) if rec else None
    if cap and cap[0]:
        vfr, ifr, note = float(cap[0]), float(cap[1]), cap[2]
        # profile_year is optional (not a SPEC §3 minimum column); SFO and BOS use the 2019 editions.
        year = str(int(cap[3])) if cap[3] is not None else "2014"
        drop = 100.0 * (vfr - ifr) / vfr
        evidence.append(EvidenceItem(
            key="ifr_arrival_drop", label=f"Arrival rate drop in bad weather (IFR {ifr:g}/hr vs VFR {vfr:g}/hr)",
            value=r1(drop), unit="%", source=f"FAA Airport Capacity Profile ({year}): {note}", as_of=year,
            strength=r1(min(100.0, drop * IFR_DROP_STRENGTH_PER_PCT))))
    else:
        caveats.append(f"{code} is not in the hand-coded runway capacity table, so no IFR vs VFR arrival-rate "
                       "drop is available.")

    # Full aircraft: share of route-months with LF > 0.85 (national distribution over all origins).
    rm_all = route_months(conn, mf.t100_months) if mf.t100_months else pd.DataFrame(
        columns=["origin", "dest", "year", "month", "passengers", "seats", "lf"])
    full = (rm_all.assign(full=rm_all["lf"] > HIGH_LF).groupby("origin")["full"].mean() * 100.0)
    df["full_route_month_share"] = full.reindex(df.index)
    national("full_route_month_share", f"Route-months with Load Factor above {HIGH_LF:.2f} (class F)", "%",
             t100_name, t100_asof)
    national("load_factor", "Load Factor, scheduled passenger flights (class F)", "%", t100_name, t100_asof)

    # Supply vs demand growth: passengers vs seats, last 12 vs prior 12 months.
    if not is_missing(df.at[code, "pax_growth_pct"]):
        df["pax_minus_seat_growth_pp"] = df["pax_growth_pct"] - df["seat_growth_pct"]
        national("pax_growth_pct", "Passenger growth, last 12 vs prior 12 months (class F)", "%", t100_name,
                 t100_asof, strength=False)
        national("seat_growth_pct", "Seat growth, last 12 vs prior 12 months (class F)", "%", t100_name,
                 t100_asof, strength=False)
        national("pax_minus_seat_growth_pp", "Passenger growth minus seat growth (supply not keeping up when "
                 "positive)", "pp", t100_name, t100_asof)
    else:
        caveats.append("The Snapshot has fewer than 24 T-100 months, so passenger vs seat growth is unavailable.")

    # Forecast Gap: TAF FY2024 → FY2030.
    gap = None
    if has_table(conn, "taf"):
        f = conn.execute("""SELECT fiscal_year, enplanements_total, ops_air_carrier FROM taf
                            WHERE iata = ? AND fiscal_year IN (?, ?)""", [code, TAF_BASE_FY, TAF_GAP_FY]).fetchall()
        by_fy = {int(fy): (e, o) for fy, e, o in f}
        if TAF_BASE_FY in by_fy and TAF_GAP_FY in by_fy and by_fy[TAF_BASE_FY][0]:
            (e0, o0), (e1, o1) = by_fy[TAF_BASE_FY], by_fy[TAF_GAP_FY]
            ops_ok = o0 is not None and o1 is not None and o0 > 0
            gap = ForecastGap(
                from_fy=TAF_BASE_FY, to_fy=TAF_GAP_FY, enplanements_from=float(e0), enplanements_to=float(e1),
                enplanements_abs=float(e1 - e0), enplanements_pct=r1(100.0 * (e1 - e0) / e0),
                ops_from=float(o0) if ops_ok else None, ops_to=float(o1) if ops_ok else None,
                ops_abs=float(o1 - o0) if ops_ok else None, ops_pct=r1(100.0 * (o1 - o0) / o0) if ops_ok else None)
            assumptions.append(f"Forecast Gap = FAA TAF 2025 total enplanements (air carrier + air taxi + commuter "
                               f"+ international) and air-carrier operations, FY{TAF_BASE_FY} actual → "
                               f"FY{TAF_GAP_FY} forecast (fiscal years Oct–Sep).")
    if gap is None:
        caveats.append(f"No FAA TAF record for {code} FY{TAF_BASE_FY}→FY{TAF_GAP_FY}; Forecast Gap unavailable.")

    # Spill Scenario: sensitivity only, never observed.
    scenario = None
    if mf.t100_months:
        scenario = spill_scenario(rm_all[rm_all["origin"] == code])
        assumptions += scenario.parameters

    drivers = sorted((e for e in evidence if e.strength is not None and e.strength > DRIVER_MIN_STRENGTH
                      and (e.key not in DRIVER_REQUIRES_POSITIVE or (e.value or 0) > 0)),
                     key=lambda e: (-e.strength, e.key))
    why = [_driver_text(e) for e in drivers] or [
        "No observed constraint indicator is above the national median for this airport."]

    srcs = [s for s in (ontime_src, t100_src, table_source("runway_capacity"),
                        table_source("taf", window=f"FY{TAF_BASE_FY} actual → FY{TAF_GAP_FY} forecast")) if s]
    caveats.append("The Spill Scenario is a sensitivity under assumed spill rates, not observed turned-away "
                   "passengers; full aircraft alone do not prove passengers were turned away.")
    return ToolResult[UnmetDemandData](
        data=UnmetDemandData(iata=code, name=df.at[code, "name"], constraint_evidence=evidence, forecast_gap=gap,
                             spill_scenario=scenario, cannot_determine=list(CANNOT_DETERMINE), why_drivers=why),
        sources=srcs,
        assumptions=assumptions,
        data_confidence=DataConfidence(level="Medium", reasons=[
            ("Unmet Demand is argued from observed indicators and an official forecast; turned-away passengers "
             "are not observed in any public data."),
            "The Spill Scenario rests on assumed, uncalibrated spill rates.",
            f"Windows: T-100 {mf.t100_window}; On-Time {mf.ontime_window}.",
        ]),
        caveats=caveats,
    )


def _driver_text(e: EvidenceItem) -> str:
    unit = "%" if e.unit == "%" else f" {e.unit}"
    bench = f" vs national median {e.benchmark}{unit}" if e.benchmark is not None else ""
    pct = f" (national percentile {e.strength:g})" if e.key != "ifr_arrival_drop" else ""
    return f"{e.label}: {e.value}{unit}{bench}{pct}."
