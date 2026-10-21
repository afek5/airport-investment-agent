"""The one way to read the Snapshot (SPEC §3): a read-only DuckDB with one view per table.

At first use we write a tiny DuckDB catalog file holding only views over
data/snapshot/*.parquet (absolute paths), then reopen it with
read_only=True. `get_conn()` returns a cursor of that shared connection,
safe to use from worker threads.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = Path(os.environ.get("SNAPSHOT_DIR", ROOT / "data" / "snapshot")).resolve()

_lock = threading.Lock()
_db: duckdb.DuckDBPyConnection | None = None


def tables() -> list[str]:
    return sorted(p.stem for p in SNAPSHOT_DIR.glob("*.parquet"))


def _open() -> duckdb.DuckDBPyConnection:
    catalog = Path(tempfile.mkdtemp(prefix="snapshot-")) / "snapshot.duckdb"
    with duckdb.connect(str(catalog)) as w:
        for name in tables():
            path = str(SNAPSHOT_DIR / f"{name}.parquet").replace("'", "''")
            w.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    return duckdb.connect(str(catalog), read_only=True)


def get_conn() -> duckdb.DuckDBPyConnection:
    """A read-only DuckDB cursor with one view per Snapshot table."""
    global _db
    with _lock:
        if _db is None:
            _db = _open()
        return _db.cursor()


@lru_cache(maxsize=1)
def manifest() -> dict:
    """data/snapshot/manifest.json: per table source, url, as_of, window, months, rows, built_at."""
    return json.loads((SNAPSHOT_DIR / "manifest.json").read_text())


def table_meta(name: str) -> dict:
    return manifest()["tables"][name]


def use_snapshot_dir(path: str | Path) -> None:
    """Point the module at another Snapshot directory (tests use small fixtures)."""
    global SNAPSHOT_DIR, _db
    with _lock:
        SNAPSHOT_DIR = Path(path).resolve()
        if _db is not None:
            _db.close()
        _db = None
    manifest.cache_clear()
