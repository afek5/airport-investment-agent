"""Small shared helpers for the analytics tools: windows, sources, rounding, Data Confidence."""

from __future__ import annotations

import math

from app.analytics.constants import HIGH_COVERAGE, MEDIUM_MIN_COVERAGE, SOURCE_NAMES
from app.contracts import ConfidenceLevel, Source
from app.snapshot import manifest

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_LEVEL_ORDER = {"Low": 0, "Medium": 1, "High": 2}


def r1(x: float | None) -> float | None:
    """Round to 1 decimal; None and NaN stay None."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), 1)


def is_missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def has_table(conn, name: str) -> bool:
    return conn.execute(
        "SELECT count(*) FROM duckdb_views() WHERE view_name = ? AND NOT internal", [name]
    ).fetchone()[0] > 0


def last_months(conn, table: str, n: int, offset: int = 0) -> list[tuple[int, int]]:
    """The `n` latest (year, month) pairs in `table`, skipping the `offset` latest, ascending."""
    if not has_table(conn, table):
        return []
    rows = conn.execute(
        f"SELECT DISTINCT year, month FROM {table} ORDER BY year DESC, month DESC LIMIT ? OFFSET ?", [n, offset]
    ).fetchall()
    return sorted((int(y), int(m)) for y, m in rows)


def window_label(months: list[tuple[int, int]]) -> str:
    if not months:
        return "no months available"
    (y0, m0), (y1, m1) = months[0], months[-1]
    return f"{len(months)} months, {_MON[m0 - 1]} {y0}–{_MON[m1 - 1]} {y1}"


def month_label(ym: tuple[int, int]) -> str:
    return f"{_MON[ym[1] - 1]} {ym[0]}"


def in_months(months: list[tuple[int, int]]) -> tuple[str, list[int]]:
    """SQL predicate + params selecting rows whose (year, month) is in `months`."""
    keys = [y * 100 + m for y, m in months] or [-1]
    return f"(year * 100 + month) IN ({','.join('?' * len(keys))})", keys


def table_source(table: str, window: str | None = None, as_of: str | None = None) -> Source | None:
    """A `Source` for a Snapshot table from the manifest; None when the table isn't in the Snapshot."""
    meta = manifest().get("tables", {}).get(table)
    if meta is None:
        return None
    url = meta.get("url", "")
    if isinstance(url, list):
        url = url[0] if url else ""
    return Source(name=meta.get("source") or SOURCE_NAMES.get(table, table), url=url or "",
                  as_of=as_of or str(meta.get("as_of", "")), window=window or meta.get("window"))


def sources(*items: Source | None) -> list[Source]:
    return [s for s in items if s is not None]


def coverage_level(measured: int) -> ConfidenceLevel:
    if measured >= HIGH_COVERAGE:
        return "High"
    if measured >= MEDIUM_MIN_COVERAGE:
        return "Medium"
    return "Low"


def lowest_level(levels: list[ConfidenceLevel]) -> ConfidenceLevel:
    return min(levels, key=_LEVEL_ORDER.__getitem__) if levels else "Low"


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
