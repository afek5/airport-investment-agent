"""query_snapshot: the guarded ad-hoc SQL escape hatch over the Snapshot views (SPEC §5).

Guards, in order:
1. DuckDB's own parser: exactly one statement, of type SELECT (WITH … SELECT included).
   INSERT, ATTACH, COPY, PRAGMA, SET, CREATE, … are rejected.
2. The parsed tree may reference only Snapshot views (or its own CTEs): no table functions
   (read_csv, read_parquet, glob, …) and no file paths as tables.
3. It runs on the read-only Snapshot connection, is interrupted after 5 s and returns ≤ 200 rows.
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
import math
import threading

import duckdb

from app.analytics.common import table_source
from app.analytics.constants import QUERY_ROW_CAP, QUERY_TIMEOUT_S
from app.contracts import AdHocData, DataConfidence, ToolResult
from app.snapshot import get_conn, tables


class UnsafeQueryError(ValueError):
    """The SQL is not a single read-only SELECT over the Snapshot views."""


def _walk(node, found_tables: set[str], ctes: set[str]) -> None:
    if isinstance(node, dict):
        kind = node.get("type")
        if kind == "TABLE_FUNCTION":
            fn = (node.get("function") or {}).get("function_name", "?")
            raise UnsafeQueryError(f"table functions are not allowed ({fn}); query the Snapshot views only")
        if kind == "BASE_TABLE":
            if node.get("catalog_name") or node.get("schema_name"):
                raise UnsafeQueryError("schema- or catalog-qualified tables are not allowed")
            found_tables.add(node.get("table_name", ""))
        cte_map = node.get("cte_map")
        if isinstance(cte_map, dict):
            ctes.update(entry.get("key", "") for entry in cte_map.get("map", []))
        for v in node.values():
            _walk(v, found_tables, ctes)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found_tables, ctes)


def check_sql(sql: str) -> list[str]:
    """Validate `sql`; returns the Snapshot views it reads. Raises UnsafeQueryError otherwise."""
    if not sql or not sql.strip():
        raise UnsafeQueryError("empty SQL")
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as e:
        raise UnsafeQueryError(f"SQL does not parse: {e}") from e
    if len(statements) != 1:
        raise UnsafeQueryError(f"exactly one statement is allowed, got {len(statements)}")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise UnsafeQueryError(f"only SELECT/WITH queries are allowed, not {statements[0].type.name}")
    with duckdb.connect() as parser:  # an empty in-memory DB, used only to serialise the parse tree
        tree = json.loads(parser.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0])
    if tree.get("error"):
        raise UnsafeQueryError(f"only plain SELECT/WITH queries are allowed ({tree.get('error_message', '')})")
    found: set[str] = set()
    ctes: set[str] = set()
    _walk(tree.get("statements", []), found, ctes)
    views = set(tables())
    unknown = sorted(t for t in found if t not in views and t not in ctes)
    if unknown:
        raise UnsafeQueryError(f"unknown tables {unknown}; the Snapshot views are {sorted(views)}")
    return sorted(t for t in found if t in views)


def _jsonable(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    return str(v)


def query_snapshot(sql: str) -> ToolResult[AdHocData]:
    """Run one read-only SELECT/WITH query over the Snapshot views (≤ 200 rows, 5 s).
    The result is ad hoc: outside the scoring methodology, Data Confidence at most Medium."""
    used = check_sql(sql)
    conn = get_conn()
    timer = threading.Timer(QUERY_TIMEOUT_S, conn.interrupt)
    timer.start()
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(QUERY_ROW_CAP + 1)
    except duckdb.InterruptException as e:
        raise UnsafeQueryError(f"query exceeded the {QUERY_TIMEOUT_S:g} s limit") from e
    except duckdb.Error as e:
        raise ValueError(f"query failed: {e}") from e
    finally:
        timer.cancel()
    truncated = len(rows) > QUERY_ROW_CAP
    rows = [[_jsonable(v) for v in r] for r in rows[:QUERY_ROW_CAP]]

    srcs = [s for s in (table_source(t) for t in used) if s is not None]
    caveats = []
    if truncated:
        caveats.append(f"Result truncated to the first {QUERY_ROW_CAP} rows.")
    if not rows:
        caveats.append("The query returned no rows.")
    return ToolResult[AdHocData](
        data=AdHocData(sql=sql, columns=columns, rows=rows, row_count=len(rows), truncated=truncated),
        sources=srcs,
        assumptions=["Ad-hoc SQL written by the agent over the Snapshot views; the SQL is shown in the trace."],
        data_confidence=DataConfidence(level="Medium", reasons=[
            "ad-hoc query outside the scoring methodology: check the SQL and the months it covers",
            "Snapshot views: " + (", ".join(used) if used else "none"),
        ]),
        caveats=caveats,
        ad_hoc=True,
    )
