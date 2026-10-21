"""Scoring on the real Snapshot. Skipped until P1-A has built the tables each test needs."""

import pytest

from app.analytics import airport_scorecard, compare_airports, query_snapshot, rank_airports, unmet_demand
from app.snapshot import get_conn

from .conftest import require_real

NEW_ENGLAND = ["CT", "ME", "MA", "NH", "RI", "VT"]
SCORE_TABLES = ("airports", "t100_routes", "ontime_airport_month", "taf", "enplanements", "metro_population")


def test_taf_total_includes_international():
    """SPEC §3: SFO FY2024 enplanements_total = 24,765,642 (17,490,518 without us_flag + frgn_flag)."""
    require_real("taf")
    total = get_conn().execute(
        "SELECT enplanements_total FROM taf WHERE iata = 'SFO' AND fiscal_year = 2024").fetchone()[0]
    assert total == 24_765_642


def test_new_england_ranking_g1_shape():
    require_real(*SCORE_TABLES)
    r = rank_airports(states=NEW_ENGLAND)
    assert len(r.data.ranked) >= 5
    assert {a.state for a in r.data.ranked} <= set(NEW_ENGLAND)
    assert any("screening signal" in c for c in r.caveats)
    assert all(s.as_of for s in r.sources)
    for a in r.data.ranked:
        assert 1 <= a.score <= 100
        assert a.provisional == (a.coverage.measured < 7)


def test_real_determinism():
    require_real(*SCORE_TABLES)
    assert rank_airports(top_n=100).model_dump_json() == rank_airports(top_n=100).model_dump_json()
    w = {"momentum": 0.7}
    assert rank_airports(states=NEW_ENGLAND, weights=w).model_dump_json() == \
        rank_airports(states=NEW_ENGLAND, weights=w).model_dump_json()


def test_bos_scorecard_full_coverage():
    require_real(*SCORE_TABLES)
    r = airport_scorecard("BOS")
    assert r.coverage.measured == 7 and r.data.national_rank is not None


def test_lax_sna_congestion_g2_shape():
    require_real("airports", "t100_routes", "ontime_airport_month")
    r = compare_airports(["LAX", "SNA"], "congestion")
    for key in ("delay_share", "taxi_out", "cancel_rate"):
        m = next(x for x in r.data.metrics if x.key == key)
        assert all(v is not None for v in m.values.values()), key
    delay = next(x for x in r.data.metrics if x.key == "delay_share").values
    assert all(5 < v < 50 for v in delay.values())  # percents, not fractions


def test_sfo_unmet_demand_g4_shape():
    require_real(*SCORE_TABLES, "runway_capacity")
    d = unmet_demand("SFO").data
    keys = {e.key for e in d.constraint_evidence}
    assert {"delay_share", "taxi_out", "ifr_arrival_drop", "full_route_month_share"} <= keys
    assert d.forecast_gap is not None and d.forecast_gap.enplanements_from == 24_765_642
    assert d.spill_scenario is not None and 0 < d.spill_scenario.low < d.spill_scenario.high
    assert d.why_drivers
    gap = next((e for e in d.constraint_evidence if e.key == "pax_minus_seat_growth_pp"), None)
    if gap is not None and gap.value is not None and gap.value <= 0:
        assert not any(w.startswith("Passenger growth minus seat growth") for w in d.why_drivers)


def test_bos_europe_query_g6_shape():
    require_real("t100_routes")
    r = query_snapshot("SELECT year, month, SUM(departures_performed) AS deps FROM t100_routes "
                       "WHERE origin = 'BOS' AND dest_country IN ('GB','FR','DE','IE','NL','ES','IT','PT') "
                       "AND month IN (6, 7, 8) GROUP BY 1, 2 ORDER BY 1, 2")
    assert r.ad_hoc and r.data.rows and r.data_confidence.level == "Medium"


@pytest.mark.parametrize("iata", ["ANC", "SFO"])
def test_route_mix_still_works(iata):
    require_real("t100_routes")
    from app.analytics import route_mix
    assert route_mix(iata).data.passenger_departures.total > 0
