import duckdb
import pytest

from app import snapshot


def test_views_and_read_only(fixture_snapshot):
    conn = snapshot.get_conn()
    assert conn.execute("SELECT count(*) FROM airports").fetchone()[0] == 5
    with pytest.raises(duckdb.Error):
        conn.execute("CREATE TABLE x AS SELECT 1")


def test_manifest(real_snapshot):
    m = snapshot.manifest()
    t = m["tables"]["t100_routes"]
    assert t["window"].startswith("12 months") or t["window"].startswith("24 months")
    assert t["as_of"] == "Jul 2026"
