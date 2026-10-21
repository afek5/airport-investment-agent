"""query_public_api (SPEC §5, HANDOFF P4 item 2): the live SoQL escape hatch.

One guarded Socrata (SODA 2.x) query against exactly three whitelisted datasets:

- `bts_airport_month`: BTS T-100 segment summary by origin airport and month (data.bts.gov `r495-tyji`).
- `dot_airfare_pairs`: DOT Consumer Airfare Report Table 1a, airport-pair markets (data.transportation.gov `tfrh-tu9e`).
- `dot_airfare_city_pairs`: DOT Consumer Airfare Report Table 6, city-pair markets of 10+ passengers a day
  (data.transportation.gov `yj5y-b2ir`).

The agent supplies only the clause bodies ($select, $where, $group, $order) and a limit; the endpoint comes from
the whitelist, `$` and `&` are refused so no extra SoQL parameter can be smuggled in, and the limit is clamped to
1–500. It shares the Live Signal client (8 s timeout, one retry, 15-minute TTL cache). A SoQL error from Socrata
goes back to the model as a retry; an outage returns the graceful "live source unavailable" envelope. Results are
always `ad_hoc=true` with Data Confidence at most Medium, and never feed a score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app import live
from app.contracts import DataConfidence, PublicApiData, Source, ToolResult

MAX_LIMIT = 500
DEFAULT_LIMIT = 100
MAX_CLAUSE_CHARS = 1000


@dataclass(frozen=True)
class PublicDataset:
    key: str
    resource_id: str
    url: str
    name: str
    default_select: str
    caveat: str
    confidence_reason: str
    row_unit: str  # what one row is when the query neither groups nor aggregates


PUBLIC_DATASETS: dict[str, PublicDataset] = {
    d.key: d
    for d in (
        PublicDataset(
            key="bts_airport_month",
            resource_id="r495-tyji",
            url="https://data.bts.gov/resource/r495-tyji.json",
            name="BTS T-100 Segment summary by origin airport (SODA r495-tyji, ad-hoc Live Signal)",
            default_select="origin_airport_code,year,reporting_month,total_departures,total_passengers,"
                           "total_seats,total_load_factor",
            caveat="The BTS summary covers all carriers and service classes departing the airport and lags the "
                   "TranStats T-100 download by about 3 months.",
            confidence_reason="official BTS monthly T-100 summary, queried ad hoc",
            row_unit="one origin airport in one month (BTS summary record)",
        ),
        PublicDataset(
            key="dot_airfare_pairs",
            resource_id="tfrh-tu9e",
            url="https://data.transportation.gov/resource/tfrh-tu9e.json",
            name="DOT Consumer Airfare Report Table 1a, airport pairs (SODA tfrh-tu9e, ad-hoc Live Signal)",
            default_select="year,quarter,airport_1,airport_2,city1,city2,nsmiles,passengers,fare,carrier_lg,"
                           "large_ms,fare_lg,carrier_low,lf_ms,fare_low",
            caveat="Consumer Airfare Report fares are average one-way fares from the DB1B 10% ticket sample; "
                   "only the largest domestic (contiguous-US) markets are published.",
            confidence_reason="derived from the DB1B 10% ticket sample",
            row_unit="one airport-pair market in one quarter (Table 1a record)",
        ),
        PublicDataset(
            key="dot_airfare_city_pairs",
            resource_id="yj5y-b2ir",
            url="https://data.transportation.gov/resource/yj5y-b2ir.json",
            name="DOT Consumer Airfare Report Table 6, city pairs (SODA yj5y-b2ir, ad-hoc Live Signal)",
            default_select="year,quarter,city1,city2,nsmiles,passengers,fare,carrier_lg,large_ms,fare_lg,"
                           "carrier_low,lf_ms,fare_low",
            caveat="Table 6 covers contiguous-US city-pair markets averaging at least 10 passengers a day; fares "
                   "are average one-way fares from the DB1B 10% ticket sample, and a city market can span "
                   "several airports.",
            confidence_reason="derived from the DB1B 10% ticket sample",
            row_unit="one city-pair market in one quarter (Table 6 record)",
        ),
    )
}

AD_HOC_CAVEAT = ("Ad-hoc live query outside the scoring methodology: check the SoQL and the periods it covers; "
                 "it never changes an Investment Opportunity Score.")
ROUNDING = "Numeric values are rounded to 2 decimals (4 decimals below 1) as returned to the agent."

# `$` would start another SODA parameter, `&`/`#` would end this one, `;` and `|>` chain statements.
_FORBIDDEN = re.compile(r"[$&#;\x00-\x08\x0b-\x1f\x7f]|\|>")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")
_KEEP_TEXT = re.compile(r"(?:id|pk)(?:_\d+)?$|^tbl$|^year$|^quarter$")


class SoqlInputError(ValueError):
    """A clause the guard refuses (goes back to the model as a retry)."""


def clamp_limit(limit: Any) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = DEFAULT_LIMIT
    return max(1, min(n, MAX_LIMIT))


def _clause(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SoqlInputError(f"{name} must be a string")
    v = value.strip()
    if not v:
        return None
    if len(v) > MAX_CLAUSE_CHARS:
        raise SoqlInputError(f"{name} is longer than {MAX_CLAUSE_CHARS} characters")
    bad = _FORBIDDEN.search(v)
    if bad:
        raise SoqlInputError(
            f"{name} contains '{bad.group(0)!s}', which is not allowed: pass only the body of the {name} clause "
            "(no $parameters, '&', ';', '#' or '|>'); the limit goes in `limit`")
    return v


def build_params(dataset: str, select: str | None = None, where: str | None = None, group: str | None = None,
                 order: str | None = None, limit: int = DEFAULT_LIMIT) -> tuple[PublicDataset, dict[str, str], int]:
    """Validate the inputs and return (dataset, SODA params, clamped limit). The request asks for limit + 1 rows
    so the result can say exactly whether it was truncated."""
    ds = PUBLIC_DATASETS.get((dataset or "").strip())
    if ds is None:
        raise SoqlInputError(f"unknown dataset '{dataset}'; use one of: {', '.join(PUBLIC_DATASETS)}")
    n = clamp_limit(limit)
    sel = _clause("select", select)
    clauses = {"$select": sel or ds.default_select, "$where": _clause("where", where),
               "$group": _clause("group", group), "$order": _clause("order", order)}
    params = {k: v for k, v in clauses.items() if v}
    if "$group" in params and not sel:
        raise SoqlInputError("a group clause needs an explicit select listing the grouped columns and aggregates")
    params["$limit"] = str(n + 1)
    return ds, params, n


def soql_text(params: dict[str, str], limit: int) -> str:
    """The query as shown in the Evidence card and trace, one SODA parameter per line."""
    lines = [f"{k}={v}" for k, v in params.items() if k != "$limit"]
    return "\n".join([*lines, f"$limit={limit}"])


def _value(column: str, v: Any) -> Any:
    """Numbers arrive as strings; return them as numbers, rounded, except identifiers and period labels."""
    if isinstance(v, str) and _NUMBER.match(v) and not _KEEP_TEXT.search(column):
        x = float(v)
        if x.is_integer() and abs(x) < 1e15:
            return int(x)
        return round(x, 2 if abs(x) >= 1 else 4)
    if isinstance(v, str) and column in ("year", "quarter") and v.isdigit():
        return int(v)
    return v


@dataclass(frozen=True)
class Periods:
    as_of: str
    window: str | None  # Source.window
    count: int | None  # distinct periods in the returned rows
    unit: str | None  # "quarter", "month" or "year"
    text: str | None  # "100 quarters, 2001 Q2–2026 Q1"


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}{'s' if n != 1 else ''}"


def _period(rows: list[dict[str, Any]]) -> Periods:
    """The distinct periods in the rows, from year/quarter, reporting_month or year columns."""
    quarters = sorted({(int(r["year"]), int(r["quarter"])) for r in rows
                       if str(r.get("year", "")).isdigit() and str(r.get("quarter", "")).isdigit()})
    if quarters:
        (y0, q0), (y1, q1) = quarters[0], quarters[-1]
        span = f"{y0} Q{q0}" if quarters[0] == quarters[-1] else f"{y0} Q{q0}–{y1} Q{q1}"
        text = f"{_plural(len(quarters), 'quarter')}, {span}"
        return Periods(f"{y1} Q{q1}", text, len(quarters), "quarter", text)
    months = sorted({str(r["reporting_month"])[:7] for r in rows if r.get("reporting_month")})
    if months:
        def label(ym: str) -> str:
            return f"{live.MONTHS[int(ym[5:7]) - 1]} {ym[:4]}"
        span = label(months[0]) if len(months) == 1 else f"{label(months[0])}–{label(months[-1])}"
        text = f"{_plural(len(months), 'month')}, {span}"
        return Periods(label(months[-1]), text, len(months), "month", text)
    years = sorted({int(r["year"]) for r in rows if str(r.get("year", "")).isdigit()})
    if years:
        span = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
        return Periods(str(years[-1]), span, len(years), "year", f"{_plural(len(years), 'year')}, {span}")
    return Periods("as queried", None, None, None, None)


_AGGREGATE = re.compile(r"\b(avg|sum|count|min|max)\s*\(", re.IGNORECASE)


def _row_meaning(ds: PublicDataset, params: dict[str, str], row_count: int, p: Periods) -> str:
    """The assumption line that says what one row is and how the row count relates to the period count."""
    if "$group" in params:
        what = f"one group of the query's GROUP BY columns ({params['$group']})"
    elif _AGGREGATE.search(params.get("$select", "")):
        what = "one aggregate over every matching record"
    else:
        what = ds.row_unit
    line = f"One row is {what}. The result has {_plural(row_count, 'row')}"
    if p.count is None:
        return line + " and no period columns, so it states no period count."
    line += f" covering {_plural(p.count, 'distinct ' + str(p.unit))} ({p.text.split(', ', 1)[1]})"
    if p.count == row_count:
        return line + f": one row per {p.unit}."
    return line + f", so one {p.unit} can span several rows; count {p.unit}s from `periods`, rows from `row_count`."


async def query_public_api(dataset: str, select: str | None = None, where: str | None = None,
                           group: str | None = None, order: str | None = None,
                           limit: int = DEFAULT_LIMIT) -> ToolResult[PublicApiData]:
    ds, params, n = build_params(dataset, select, where, group, order, limit)
    soql = soql_text(params, n)

    def data(columns: list[str], rows: list[list[Any]], truncated: bool, p: Periods | None = None) -> PublicApiData:
        return PublicApiData(sql=soql, columns=columns, rows=rows, row_count=len(rows), truncated=truncated,
                             dataset=ds.key, resource_id=ds.resource_id, endpoint=ds.url, limit=n,
                             period_count=p.count if p else None, periods=p.text if p else None)

    try:
        raw = await live._fetch(ds.url, params, soql_errors=True)  # noqa: SLF001 - shared Live Signal client
        if not isinstance(raw, list):
            raise live.LiveSourceError(f"unexpected {type(raw).__name__} response")
    except live.LiveSourceError as e:
        env = live._unavailable(data([], [], False), ds.name, ds.url, e)  # noqa: SLF001
        return env.model_copy(update={"ad_hoc": True, "caveats": [*env.caveats, AD_HOC_CAVEAT]})

    truncated = len(raw) > n
    records = [r for r in raw[:n] if isinstance(r, dict)]
    columns: list[str] = []
    for r in records:
        columns.extend(k for k in r if k not in columns)
    rows = [[_value(c, r.get(c)) for c in columns] for r in records]
    p = _period(records)
    assumptions = [f"Ad-hoc SoQL over {ds.resource_id} written by the agent; the query is shown with the result.",
                   ROUNDING]
    if records:
        assumptions.append(_row_meaning(ds, params, len(rows), p))
    if truncated:
        assumptions.append(f"Only the first {n} rows were returned (limit {n}); more rows match the query, so "
                           "the period count covers the returned rows only.")
    if not records:
        return ToolResult[PublicApiData](
            data=data(columns, rows, truncated),
            sources=[Source(name=ds.name, url=ds.url, as_of="none")],
            assumptions=assumptions,
            data_confidence=DataConfidence(level="Low", reasons=[f"the query on {ds.resource_id} returned no rows"]),
            caveats=[ds.caveat, AD_HOC_CAVEAT],
            ad_hoc=True,
        )
    return ToolResult[PublicApiData](
        data=data(columns, rows, truncated, p),
        sources=[Source(name=ds.name, url=ds.url, as_of=p.as_of, window=p.window)],
        assumptions=assumptions,
        data_confidence=DataConfidence(level="Medium", reasons=[
            "ad-hoc query outside the scoring methodology", ds.confidence_reason]),
        caveats=[ds.caveat, AD_HOC_CAVEAT],
        ad_hoc=True,
    )
