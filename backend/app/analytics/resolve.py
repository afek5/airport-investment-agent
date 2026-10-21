"""resolve_airports: names, cities and codes → Primary Airport candidates."""

from __future__ import annotations

import re

from app.analytics.constants import AIRPORT_ALIASES, FAA_ENPL_SOURCE_NAME, FAA_ENPL_URL
from app.contracts import AirportCandidate, DataConfidence, ResolveData, Source, ToolResult
from app.snapshot import get_conn, table_meta

_COLS = "iata, name, city, state, hub_size, is_primary"


def _candidate(row: tuple, match: str) -> AirportCandidate:
    iata, name, city, state, hub, primary = row
    return AirportCandidate(iata=iata, name=name, city=city, state=state, hub_size=hub,
                            is_primary=bool(primary), match=match)


def resolve_airports(query: str) -> ToolResult[ResolveData]:
    conn = get_conn()
    q = query.strip()
    key = re.sub(r"[^a-z ]", "", q.lower()).strip()
    key = re.sub(r"\s+(airport|international|intl)$", "", key)
    assumptions: list[str] = []
    candidates: list[AirportCandidate] = []
    alternates: list[str] = []
    level, reason = "High", "exact airport code match"

    def by_codes(codes: list[str]) -> dict[str, tuple]:
        if not codes:
            return {}
        rows = conn.execute(f"SELECT {_COLS} FROM airports WHERE iata IN ({','.join('?' * len(codes))})",
                            codes).fetchall()
        return {r[0]: r for r in rows}

    code = q.upper()
    if re.fullmatch(r"[A-Z0-9]{3,4}", code):
        row = conn.execute(f"SELECT {_COLS} FROM airports WHERE iata = ? OR icao = ? OR faa_locid = ?",
                           [code, code, code]).fetchone()
        if row:
            candidates.append(_candidate(row, "code"))

    if not candidates and key in AIRPORT_ALIASES:
        primary, alts, note = AIRPORT_ALIASES[key]
        found = by_codes([primary, *alts])
        if primary in found:
            candidates.append(_candidate(found[primary], "alias"))
        candidates += [_candidate(found[a], "alias") for a in alts if a in found]
        alternates = [a for a in alts if a in found]
        assumptions.append(note + (f"; alternates: {', '.join(alternates)}" if alternates else ""))
        reason = "alias table match"

    if not candidates and len(key) >= 3:
        like = f"%{key}%"
        rows = conn.execute(
            f"SELECT {_COLS} FROM airports WHERE lower(city) LIKE ? OR lower(name) LIKE ? "
            "ORDER BY CASE hub_size WHEN 'L' THEN 0 WHEN 'M' THEN 1 WHEN 'S' THEN 2 ELSE 3 END, iata LIMIT 6",
            [like, like]).fetchall()
        candidates = [_candidate(r, "name") for r in rows]
        if candidates:
            alternates = [c.iata for c in candidates[1:]]
            level, reason = "Medium", "name/city text match"
            assumptions.append(f"'{q}' = {candidates[0].iata} ({candidates[0].name})"
                               + (f"; alternates: {', '.join(alternates)}" if alternates else ""))

    if not candidates:
        level, reason = "Low", f"no Primary Airport matched '{q}'"

    meta = table_meta("airports")
    return ToolResult[ResolveData](
        data=ResolveData(query=q, resolved=candidates[0].iata if candidates else None,
                         candidates=candidates, alternates=alternates),
        sources=[Source(name=FAA_ENPL_SOURCE_NAME + " + OurAirports", url=FAA_ENPL_URL, as_of=meta["as_of"])],
        assumptions=assumptions,
        data_confidence=DataConfidence(level=level, reasons=[reason]),
        caveats=["The universe is FAA Primary Airports (more than 10,000 boardings a year)."],
    )
