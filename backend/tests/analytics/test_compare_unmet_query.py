"""compare_airports (congestion lens), unmet_demand (spill buckets, evidence, cannot_determine) and the
query_snapshot SQL guard, on the hand-made Snapshot in conftest.py."""

import pandas as pd
import pytest

from app.analytics import UnsafeQueryError, compare_airports, query_snapshot, unmet_demand
from app.analytics import query as query_mod
from app.analytics.constants import CANNOT_DETERMINE, SPILL_LABEL
from app.analytics.unmet import spill_rates, spill_scenario
from app.contracts import AdHocData, ComparisonData, ToolResult, UnmetDemandData

# ───────────── compare_airports ─────────────


def _metric(r, key):
    return next(m for m in r.data.metrics if m.key == key)


def test_congestion_lens_values_and_percentiles(scoring_snapshot):
    r = compare_airports(["sfo", "BOS"], "congestion")
    assert r.data.iatas == ["SFO", "BOS"]
    delay = _metric(r, "delay_share")
    assert delay.values == {"SFO": 30.0, "BOS": 25.0}  # stored as fractions, returned as %
    assert delay.percentiles == {"SFO": 100.0, "BOS": 80.0}
    assert _metric(r, "taxi_out").values == {"SFO": 22.0, "BOS": 20.0}
    assert _metric(r, "cancel_rate").values == {"SFO": 1.0, "BOS": 1.0}
    assert _metric(r, "nas_delay_min_per_flight").values == {"SFO": 6.0, "BOS": 2.0}
    assert _metric(r, "monthly_departures").values == {"SFO": 15.0, "BOS": 15.0}  # 10 F + 5 G per month
    # 180 departures in 12 months / 365.25 days / runways
    assert _metric(r, "deps_per_runway_day").values == {"SFO": round(180 / 365.25 / 4, 1), "BOS": round(180 / 365.25 / 6, 1)}
    # congestion_index = mean percentile of delay share, taxi-out, NAS delay
    nas = _metric(r, "nas_delay_min_per_flight").percentiles
    assert r.data.congestion_index["SFO"] == round((100 + 100 + nas["SFO"]) / 3, 1)
    assert any("not the Investment Opportunity Score" in a for a in r.assumptions)
    assert r.data_confidence.level == "High"


def test_congestion_lens_marks_thin_on_time_coverage(scoring_snapshot):
    r = compare_airports(["SFO", "PWM"])
    assert _metric(r, "delay_share").values["PWM"] is None
    assert r.data.congestion_index["PWM"] is None
    assert r.data_confidence.level == "Medium"
    assert any("PWM" in x for x in r.data_confidence.reasons)


def test_demand_and_scorecard_lenses(scoring_snapshot):
    d = compare_airports(["BOS", "BDL"], "demand")
    assert _metric(d, "enpl_yoy").values == {"BOS": 5.0, "BDL": 10.0}
    assert _metric(d, "pax_growth_pct").values["BOS"] == round(100 * (700 / 650 - 1), 1)
    s = compare_airports(["BOS", "BTV"], "scorecard")
    assert _metric(s, "score").values["BTV"] is None
    assert _metric(s, "coverage_measured").values == {"BOS": 7.0, "BTV": 3.0}
    assert any("screening signal" in c for c in s.caveats)


def test_compare_validation(scoring_snapshot):
    with pytest.raises(ValueError):
        compare_airports(["BOS"])
    with pytest.raises(ValueError):
        compare_airports(["BOS", "XYZ"])  # not primary
    with pytest.raises(ValueError):
        compare_airports(["BOS", "BDL"], "vibes")


# ───────────── unmet_demand ─────────────


def test_spill_buckets():
    assert spill_rates(0.85) is None  # LF must exceed 0.85
    assert spill_rates(0.86) == (0.02, 0.05)
    assert spill_rates(0.90) == (0.02, 0.05)  # upper bound inclusive
    assert spill_rates(0.92) == (0.05, 0.10)
    assert spill_rates(0.95) == (0.05, 0.10)
    assert spill_rates(0.96) == (0.10, 0.15)
    assert spill_rates(1.02) == (0.10, 0.15)


def test_spill_scenario_sums_and_top_routes():
    rm = pd.DataFrame({"dest": ["A", "A", "B", "C", "D"], "passengers": [1000] * 5,
                       "lf": [0.85, 0.86, 0.90, 0.92, 0.96]})
    s = spill_scenario(rm)
    assert (s.low, s.high) == (20 + 20 + 50 + 100, 50 + 50 + 100 + 150)
    assert [r.dest for r in s.top_routes] == ["D", "C", "A", "B"]  # by high, then code
    a = next(r for r in s.top_routes if r.dest == "A")
    assert (a.months_over_threshold, a.low, a.high) == (1, 20, 50)
    assert s.label == SPILL_LABEL and "not calibrated" in s.label
    assert any("not calibrated" in p for p in s.parameters)


def test_unmet_demand_sfo(scoring_snapshot):
    r = unmet_demand("SFO")
    d = r.data
    ev = {e.key: e for e in d.constraint_evidence}
    # observed evidence with national-median benchmarks
    assert ev["delay_share"].value == 30.0 and ev["delay_share"].benchmark == 20.0
    assert ev["taxi_out"].value == 22.0 and ev["taxi_out"].benchmark == 16.0
    assert ev["ifr_arrival_drop"].value == 50.0 and ev["ifr_arrival_drop"].strength == 100.0
    assert ev["full_route_month_share"].value == 100.0  # every SFO route-month at LF 0.90 > 0.85
    assert ev["pax_minus_seat_growth_pp"].value == round(100 * (900 / 850 - 1), 1)  # seats flat
    assert all(e.as_of and e.source for e in d.constraint_evidence)
    # drivers ordered by strength, observed evidence only
    # six indicators tie at strength 100, so the key breaks the tie: delay_share first
    assert d.why_drivers[0] == "Departures delayed ≥15 min: 30.0% vs national median 20.0% (national percentile 100)."
    assert any(w.startswith("Arrival rate drop in bad weather (IFR 30/hr vs VFR 60/hr): 50.0%") for w in d.why_drivers)
    assert not any("Passenger growth minus seat growth" in w for w in d.why_drivers)  # below the median
    # Forecast Gap FY2024 → FY2030 (TAF total incl. international)
    g = d.forecast_gap
    assert (g.from_fy, g.to_fy, g.enplanements_from) == (2024, 2030, 24_765_642)
    assert g.enplanements_pct == 15.0 and g.ops_abs == 400_000 - 350_805
    # scenario: 12 route-months at LF 0.90 with 900 pax → 2–5 %
    assert (d.spill_scenario.low, d.spill_scenario.high) == (round(12 * 900 * 0.02), round(12 * 900 * 0.05))
    assert d.cannot_determine == CANNOT_DETERMINE
    assert r.data_confidence.level == "Medium"
    assert isinstance(ToolResult[UnmetDemandData].model_validate_json(r.model_dump_json()).data, UnmetDemandData)


def test_unmet_demand_without_runway_capacity_says_so(scoring_snapshot):
    r = unmet_demand("BOS")
    assert "ifr_arrival_drop" not in {e.key for e in r.data.constraint_evidence}
    assert any("not in the hand-coded runway capacity table" in c for c in r.caveats)


# ───────────── query_snapshot guard ─────────────


@pytest.mark.parametrize("sql", [
    "INSERT INTO airports VALUES (1)",
    "ATTACH 'x.db' AS x",
    "COPY airports TO 'out.csv'",
    "PRAGMA database_list",
    "SET threads = 1",
    "CREATE TABLE t AS SELECT 1",
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP VIEW airports",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM '/etc/passwd'",
    "SELECT * FROM glob('*')",
    "SELECT * FROM airports WHERE iata IN (SELECT * FROM read_text('/etc/hosts'))",
    "SELECT * FROM secret_table",
    "SELECT * FROM main.airports",
    "",
    "SELEC nonsense",
])
def test_sql_guard_rejects(scoring_snapshot, sql):
    with pytest.raises(UnsafeQueryError):
        query_snapshot(sql)


def test_sql_guard_accepts_select_and_with(scoring_snapshot):
    r = query_snapshot("WITH bos AS (SELECT * FROM t100_routes WHERE origin = 'BOS') "
                       "SELECT dest_country, SUM(departures_performed) AS deps FROM bos GROUP BY 1 ORDER BY 1")
    assert r.ad_hoc and r.data_confidence.level == "Medium"
    assert r.data.columns == ["dest_country", "deps"] and r.data.rows == [["US", 360]]
    assert [s.name for s in r.sources] == ["fixture t100_routes"]
    assert isinstance(ToolResult[AdHocData].model_validate_json(r.model_dump_json()).data, AdHocData)


def test_query_row_cap(scoring_snapshot):
    r = query_snapshot("SELECT * FROM t100_routes")
    assert r.data.row_count == 200 and r.data.truncated
    assert any("truncated" in c for c in r.caveats)


def test_query_timeout(scoring_snapshot, monkeypatch):
    monkeypatch.setattr(query_mod, "QUERY_TIMEOUT_S", 0.05)
    with pytest.raises(UnsafeQueryError, match="limit"):
        query_snapshot("SELECT count(*) FROM t100_routes a, t100_routes b, t100_routes c, t100_routes d "
                       "WHERE a.seats + b.seats + c.seats + d.seats > 0")


def test_compare_envelope_validates(scoring_snapshot):
    r = compare_airports(["SFO", "BOS"])
    assert isinstance(ToolResult[ComparisonData].model_validate_json(r.model_dump_json()).data, ComparisonData)
