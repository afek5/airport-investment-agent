"""Live Signals (SPEC §5): three keyless government APIs called at question time.

- BTS SODA `r495-tyji`: T-100 segment summary by origin airport and month (`live_traffic`).
- DOT SODA `tfrh-tu9e`: Consumer Airfare Report Table 1a, airport-pair O&D demand and fares (`od_demand`).
- FAA NAS Status XML: current delays, ground stops and closures (`live_delays`).
- `query_public_api` (app.live.public_api): the guarded ad-hoc SoQL escape hatch over a three-dataset whitelist.

Each call has an 8 s timeout, one retry and a 15-minute in-process TTL cache. On failure the tool
returns the normal envelope with empty data, Data Confidence Low and the caveat
"live source unavailable; answering from Snapshot as of …". Live Signals never feed a score.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

from app.contracts import (
    DataConfidence, LiveDelay, LiveDelaysData, LiveTrafficData, LiveTrafficMonth, OdDemandData, OdMarket, Source,
    ToolResult,
)

log = logging.getLogger(__name__)

TIMEOUT_S = 8.0
RETRIES = 1
RETRY_DELAY_S = 0.5
CACHE_TTL_S = 15 * 60
USER_AGENT = "airport-investment-agent/0.1 (public-data research demo)"

BTS_URL = "https://data.bts.gov/resource/r495-tyji.json"
DOT_URL = "https://data.transportation.gov/resource/tfrh-tu9e.json"
NAS_URL = "https://nasstatus.faa.gov/api/airport-status-information"

BTS_NAME = "BTS T-100 Segment summary by origin airport (SODA r495-tyji, Live Signal)"
DOT_NAME = "DOT Consumer Airfare Report Table 1a (SODA tfrh-tu9e, Live Signal)"
NAS_NAME = "FAA NAS Status (Live Signal)"

LIVE_CAVEAT = "Live Signal: it informs the explanation and never changes an Investment Opportunity Score."
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_IATA = re.compile(r"^[A-Z0-9]{3}$")

# Tests swap in an httpx.MockTransport; production uses the default transport.
transport: httpx.AsyncBaseTransport | None = None
_cache: dict[str, tuple[float, Any]] = {}


class LiveSourceError(RuntimeError):
    pass


class SoqlQueryError(ValueError):
    """Socrata rejected the query itself (HTTP 400); not retried, the caller can fix the query."""


def clear_cache() -> None:
    _cache.clear()


def _iata(code: str) -> str:
    c = code.strip().upper()
    if c.startswith("K") and len(c) == 4:
        c = c[1:]
    if not _IATA.match(c):
        raise ValueError(f"'{code}' is not a 3-letter airport code; call resolve_airports first")
    return c


async def _fetch(url: str, params: dict[str, str] | None = None, *, as_text: bool = False,
                 soql_errors: bool = False) -> Any:
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport, headers={"User-Agent": USER_AGENT},
                                 follow_redirects=True) as client:
        for attempt in range(RETRIES + 1):
            try:
                r = await client.get(url, params=params)
                if r.status_code >= 500 or r.status_code == 429:
                    raise LiveSourceError(f"HTTP {r.status_code}")
                if soql_errors and r.status_code == 400:
                    raise SoqlQueryError(_soql_message(r))
                r.raise_for_status()
                value = r.text if as_text else r.json()
                _cache[key] = (time.monotonic(), value)
                return value
            except SoqlQueryError:
                raise
            except (httpx.HTTPError, LiveSourceError, ValueError) as e:
                last = e
                log.warning("live fetch %s failed (attempt %d): %s", url, attempt + 1, e)
                if attempt < RETRIES:
                    await asyncio.sleep(RETRY_DELAY_S)
    raise LiveSourceError(f"{type(last).__name__}: {last}")


def _soql_message(r: httpx.Response) -> str:
    try:
        body = r.json()
        msg = str(body.get("message") or r.text) if isinstance(body, dict) else r.text
    except ValueError:
        msg = r.text
    return f"Socrata rejected the query: {msg.split(chr(10))[0][:300]}"


def _snapshot_as_of() -> str:
    try:
        from app.snapshot import table_meta

        return f"T-100 {table_meta('t100_routes')['as_of']}"
    except Exception:  # noqa: BLE001 - the fallback text must never fail
        return "the latest build"


def _unavailable(data: Any, name: str, url: str, err: Exception) -> ToolResult:
    as_of = _snapshot_as_of()
    return ToolResult[type(data)](
        data=data,
        sources=[Source(name=name, url=url, as_of="unavailable")],
        data_confidence=DataConfidence(level="Low", reasons=[f"live source unavailable ({err})"]),
        caveats=[f"live source unavailable; answering from Snapshot as of {as_of}", LIVE_CAVEAT],
    )


def _int(v: Any) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _float(v: Any, nd: int = 1) -> float | None:
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


def _pct(share: Any) -> float | None:
    v = _float(share, 6)
    return None if v is None else round(v * 100, 1)


def _label(y: int, m: int) -> str:
    return f"{MONTHS[m - 1]} {y}"


# ───────────────────────────── live_traffic ─────────────────────────────


async def live_traffic(iata: str, months: int = 12) -> ToolResult[LiveTrafficData]:
    code = _iata(iata)
    months = max(1, min(int(months), 36))
    params = {
        "$select": "year,reporting_month,total_departures,total_passengers,total_seats,total_load_factor",
        "$where": f"origin_airport_code='{code}'",
        "$order": "reporting_month DESC",
        "$limit": str(months),
    }
    try:
        rows = await _fetch(BTS_URL, params)
    except LiveSourceError as e:
        return _unavailable(LiveTrafficData(iata=code, months=[]), BTS_NAME, BTS_URL, e)

    out: list[LiveTrafficMonth] = []
    for r in rows:
        try:
            d = datetime.fromisoformat(str(r["reporting_month"])[:10])
        except (KeyError, ValueError):
            continue
        out.append(LiveTrafficMonth(year=d.year, month=d.month, departures=_int(r.get("total_departures")),
                                    passengers=_int(r.get("total_passengers")), seats=_int(r.get("total_seats")),
                                    load_factor_pct=_float(r.get("total_load_factor"))))
    out.sort(key=lambda m: (m.year, m.month))
    data = LiveTrafficData(iata=code, months=out)
    if not out:
        return ToolResult[LiveTrafficData](
            data=data, sources=[Source(name=BTS_NAME, url=BTS_URL, as_of="none")],
            data_confidence=DataConfidence(level="Low", reasons=[f"BTS returned no monthly rows for {code}"]),
            caveats=[LIVE_CAVEAT])
    first, last = out[0], out[-1]
    window = f"{len(out)} months, {_label(first.year, first.month)}–{_label(last.year, last.month)}"
    return ToolResult[LiveTrafficData](
        data=data,
        sources=[Source(name=BTS_NAME, url=BTS_URL, as_of=_label(last.year, last.month), window=window)],
        assumptions=["All carriers and all service classes departing the airport, as BTS publishes them; "
                     "load_factor_pct is BTS's total_load_factor."],
        data_confidence=DataConfidence(level="High", reasons=["official BTS monthly T-100 summary"]),
        caveats=["The BTS summary lags the TranStats T-100 download by about 3 months, so it can end earlier "
                 "than the Snapshot.", LIVE_CAVEAT],
    )


# ───────────────────────────── od_demand ─────────────────────────────


async def od_demand(iata: str, top_n: int = 10) -> ToolResult[OdDemandData]:
    code = _iata(iata)
    top_n = max(1, min(int(top_n), 25))
    either = f"(airport_1='{code}' OR airport_2='{code}')"
    try:
        latest = await _fetch(DOT_URL, {"$select": "year,quarter", "$where": either,
                                        "$order": "year DESC,quarter DESC", "$limit": "1"})
        if not latest:
            data = OdDemandData(iata=code, year=None, quarter=None, markets=[])
            return ToolResult[OdDemandData](
                data=data, sources=[Source(name=DOT_NAME, url=DOT_URL, as_of="none")],
                data_confidence=DataConfidence(level="Low", reasons=[f"no Consumer Airfare Report markets for {code}"]),
                caveats=["The report covers only the largest domestic (contiguous-US) city-pair markets.", LIVE_CAVEAT])
        year, quarter = latest[0]["year"], latest[0]["quarter"]
        rows = await _fetch(DOT_URL, {"$where": f"{either} AND year='{year}' AND quarter='{quarter}'",
                                      "$limit": "1000"})
    except LiveSourceError as e:
        return _unavailable(OdDemandData(iata=code, year=None, quarter=None, markets=[]), DOT_NAME, DOT_URL, e)

    markets = []
    for r in rows:
        mine_first = r.get("airport_1") == code
        markets.append(OdMarket(
            other_airport=r.get("airport_2") if mine_first else r.get("airport_1"),
            other_city=r.get("city2") if mine_first else r.get("city1"),
            nsmiles=_float(r.get("nsmiles"), 0),
            passengers_per_day=_float(r.get("passengers"), 1),
            fare=_float(r.get("fare"), 2),
            carrier_lg=r.get("carrier_lg"),
            large_ms_pct=_pct(r.get("large_ms")),
            fare_lg=_float(r.get("fare_lg"), 2),
            carrier_low=r.get("carrier_low"),
            lf_ms_pct=_pct(r.get("lf_ms")),
            fare_low=_float(r.get("fare_low"), 2),
        ))
    markets.sort(key=lambda m: (-(m.passengers_per_day or 0), m.other_airport or ""))
    y, q = int(year), int(quarter)
    return ToolResult[OdDemandData](
        data=OdDemandData(iata=code, year=y, quarter=q, markets=markets[:top_n]),
        sources=[Source(name=DOT_NAME, url=DOT_URL, as_of=f"{y} Q{q}", window=f"{y} Q{q} (one quarter)")],
        assumptions=["passengers_per_day is the average daily one-way O&D passengers in the airport-pair market "
                     "over the quarter; large_ms_pct is the largest carrier's market share, lf_ms_pct the "
                     "lowest-fare carrier's share."],
        data_confidence=DataConfidence(level="Medium", reasons=[
            "derived from the DB1B 10% ticket sample", "one quarter of data"]),
        caveats=["The report covers only the largest domestic (contiguous-US) city-pair markets; international "
                 "and small markets are not included.", LIVE_CAVEAT],
    )


# ───────────────────────────── live_delays ─────────────────────────────


def _text(el: ET.Element | None, tag: str) -> str | None:
    if el is None:
        return None
    found = el.find(tag)
    return found.text.strip() if found is not None and found.text else None


def parse_nas(xml: str) -> tuple[str | None, list[LiveDelay]]:
    root = ET.fromstring(xml)
    update_time = _text(root, "Update_Time")
    delays: list[LiveDelay] = []
    for dt in root.iter("Delay_type"):
        for gd in dt.iter("Ground_Delay"):
            delays.append(LiveDelay(iata=_text(gd, "ARPT") or "", kind="Ground Delay Program",
                                    reason=_text(gd, "Reason"), avg_delay=_text(gd, "Avg"),
                                    max_delay=_text(gd, "Max")))
        for gs in dt.iter("Program"):
            delays.append(LiveDelay(iata=_text(gs, "ARPT") or "", kind="Ground Stop", reason=_text(gs, "Reason"),
                                    until=_text(gs, "End_Time")))
        for d in dt.iter("Delay"):
            for ad in d.iter("Arrival_Departure"):
                kind = f"{ad.get('Type') or 'General'} Delay"
                delays.append(LiveDelay(iata=_text(d, "ARPT") or "", kind=kind, reason=_text(d, "Reason"),
                                        min_delay=_text(ad, "Min"), max_delay=_text(ad, "Max"),
                                        trend=_text(ad, "Trend")))
        for a in dt.iter("Airport"):
            reason = _text(a, "Reason")
            ga_only = bool(reason and re.search(r"NON[\s-]*SKED\s+TRANSIENT\s+GA", reason, re.I))
            delays.append(LiveDelay(iata=_text(a, "ARPT") or "",
                                    kind="Closure notice (non-scheduled transient GA only)" if ga_only
                                    else "Airport Closure",
                                    reason=reason, until=_text(a, "Reopen")))
    return update_time, [d for d in delays if d.iata]


async def live_delays(iatas: list[str] | None = None) -> ToolResult[LiveDelaysData]:
    queried = [_iata(c) for c in (iatas or [])]
    try:
        xml = await _fetch(NAS_URL, as_text=True)
        update_time, delays = parse_nas(xml)
    except (LiveSourceError, ET.ParseError) as e:
        return _unavailable(LiveDelaysData(update_time=None, queried=queried, delays=[], no_active_delay=[]),
                            NAS_NAME, NAS_URL, e)
    if queried:
        delays = [d for d in delays if d.iata in queried]
    impacted = {d.iata for d in delays if not d.kind.startswith("Closure notice")}
    no_active = [c for c in queried if c not in impacted]
    caveats = ["Only airports with an active event appear in the FAA feed; an airport that is not listed has "
               "no active delay right now.", LIVE_CAVEAT]
    if any(d.kind.startswith("Closure notice") for d in delays):
        caveats.insert(0, "A 'Closure notice (non-scheduled transient GA only)' restricts only non-scheduled "
                          "general aviation; airline operations are not affected.")
    return ToolResult[LiveDelaysData](
        data=LiveDelaysData(update_time=update_time, queried=queried, delays=delays, no_active_delay=no_active),
        sources=[Source(name=NAS_NAME, url=NAS_URL, as_of=update_time or "now", window="right now")],
        data_confidence=DataConfidence(level="High", reasons=["real-time FAA NAS Status feed"]),
        caveats=caveats,
    )


# The ad-hoc SoQL escape hatch shares this module's client, cache and transport (imported last: it uses them).
from app.live.public_api import PUBLIC_DATASETS, query_public_api  # noqa: E402, F401
