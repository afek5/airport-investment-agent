"""Aggregation maths and the fail-loudly coverage checks of build_snapshot."""

import shutil

import pandas as pd
import pytest

import build_snapshot as bs


def test_aggregate_ontime_maths():
    raw = pd.DataFrame({
        "FL_DATE": ["8/1/2026 12:00:00 AM"] * 4 + ["8/2/2026 12:00:00 AM"],
        "ORIGIN": ["SFO", "SFO", "SFO", "SFO", "SNA"],
        "DEP_DELAY": [30.0, -5.0, 0.0, None, 10.0],
        "DEP_DEL15": [1.0, 0.0, 0.0, None, 0.0],
        "TAXI_OUT": [20.0, 10.0, 30.0, None, 12.0],
        "CANCELLED": [0.0, 0.0, 0.0, 1.0, 0.0],
        "NAS_DELAY": [15.0, None, None, 99.0, None],
    })
    out = bs.aggregate_ontime(raw).set_index("origin")
    sfo = out.loc["SFO"]
    assert (sfo["year"], sfo["month"]) == (2026, 8)
    assert sfo["flights"] == 4 and sfo["flights_operated"] == 3
    assert sfo["dep_del15_share"] == pytest.approx(1 / 3)
    assert sfo["avg_taxi_out_min"] == pytest.approx(20.0)
    assert sfo["cancel_rate"] == pytest.approx(0.25)
    assert sfo["nas_delay_min_per_flight"] == pytest.approx(5.0)   # the cancelled flight's NAS minutes ignored
    assert sfo["avg_dep_delay_min"] == pytest.approx(25 / 3)
    assert out.loc["SNA", "flights"] == 1


def test_aggregate_ontime_rejects_missing_column():
    with pytest.raises(bs.SnapshotError, match="NAS_DELAY"):
        bs.aggregate_ontime(pd.DataFrame({c: [] for c in bs.ONTIME_RAW_COLS if c != "NAS_DELAY"}))


def test_require_columns_fails_loudly():
    with pytest.raises(bs.SnapshotError, match=r"missing required columns \['dest_country'\]"):
        bs.require_columns(pd.DataFrame({"origin": []}), ["origin", "dest_country"], "t100_routes")


def _raw_with(tmp_path, folder: str, keep: int):
    src = sorted((bs.RAW / folder).glob(f"{folder if folder == 't100' else 'ontime'}_*.zip"))
    if not src:
        pytest.skip(f"data/raw/{folder} not present (fresh clone)")
    (tmp_path / folder).mkdir()
    for f in src[-keep:]:
        (tmp_path / folder / f.name).symlink_to(f)
    return tmp_path


def test_t100_missing_month_fails_loudly(tmp_path, monkeypatch):
    raw = _raw_with(tmp_path, "t100", keep=12)
    monkeypatch.setattr(bs, "RAW", raw)
    with pytest.raises(bs.SnapshotError, match="t100_routes: missing required months"):
        bs.build_t100_routes()


def test_ontime_below_6_months_fails_loudly(tmp_path, monkeypatch):
    raw = _raw_with(tmp_path, "ontime", keep=5)
    monkeypatch.setattr(bs, "RAW", raw)
    with pytest.raises(bs.SnapshotError, match="only 5 of 12 target months"):
        bs.build_ontime_airport_month()


def test_runway_capacity_requires_citation(tmp_path, monkeypatch):
    df = pd.read_csv(bs.RUNWAY_CAPACITY_CSV)
    df.loc[0, "source_note"] = None
    bad = tmp_path / "runway_capacity.csv"
    df.to_csv(bad, index=False)
    monkeypatch.setattr(bs, "RUNWAY_CAPACITY_CSV", bad)
    monkeypatch.setattr(bs, "OUT", tmp_path)
    shutil.copy(bs.ROOT / "data" / "snapshot" / "airports.parquet", tmp_path / "airports.parquet")
    with pytest.raises(bs.SnapshotError, match="citation"):
        bs.build_runway_capacity()


def test_taf_raw_record_component_sum():
    """SPEC §3 test: the Snapshot total equals the five-component sum of the raw FY2024 SFO record."""
    if not bs.TAF_ZIP.exists():
        pytest.skip("data/raw/taf2025.zip not present (fresh clone)")
    raw = bs.read_taf_sheet("Enplanements.xlsx", bs.TAF_ENPL_COLS)
    rec = raw[(raw["locid"] == "SFO") & (raw["ayear"] == 2024)].iloc[0]
    assert rec["scenario"] == 0
    five = bs.taf_enplanements_total(rec)
    assert five == 24_765_642
    assert int(rec["aac"] + rec["aat"] + rec["commuter"]) == 17_490_518
    snap = pd.read_parquet(bs.ROOT / "data" / "snapshot" / "taf.parquet")
    assert snap.query("iata == 'SFO' and fiscal_year == 2024")["enplanements_total"].iloc[0] == five
