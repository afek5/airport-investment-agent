from app.analytics import route_mix
from app.contracts import RouteMixData, ToolResult


def test_route_mix_maths_on_fixture(fixture_snapshot):
    r = route_mix("aaa")
    d = r.data
    # class F: 11 deps/month × 12 = 132; long-haul (≥ 3,000 mi, inclusive) = ATL only = 12
    assert (d.passenger_departures.long_haul, d.passenger_departures.total) == (12, 132)
    assert d.passenger_departures.share_pct == 9.1  # 12/132 = 9.09 %
    # passenger-weighted: 300 / 1,300 per month
    assert (d.passenger_weighted.long_haul, d.passenger_weighted.total) == (3600, 15600)
    assert d.passenger_weighted.share_pct == 23.1
    # cargo-inclusive: (1 + 10) / 21 per month
    assert (d.cargo_inclusive_departures.long_haul, d.cargo_inclusive_departures.total) == (132, 252)
    assert d.cargo_inclusive_departures.share_pct == 52.4
    assert d.non_passenger_departure_share_pct == 47.6
    assert d.window == "12 months, Aug 2025–Jul 2026"
    assert len(d.months) == 12 and "2025-07" not in d.months


def test_route_mix_threshold_is_inclusive_and_configurable(fixture_snapshot):
    assert route_mix("AAA", min_miles=2999).data.passenger_departures.long_haul == 24
    assert route_mix("AAA", min_miles=3001).data.passenger_departures.long_haul == 0


def test_route_mix_top_destinations_default_passenger_only(fixture_snapshot):
    d = route_mix("AAA").data
    assert [x.dest for x in d.top_long_haul_destinations] == ["ATL"]
    d_cargo = route_mix("AAA", include_cargo=True).data
    assert [x.dest for x in d_cargo.top_long_haul_destinations] == ["NRT", "ATL"]


def test_route_mix_envelope_and_cargo_caveat(fixture_snapshot):
    r = route_mix("AAA")
    assert isinstance(r, ToolResult) and isinstance(r.data, RouteMixData)
    assert any("3,000 statute miles" in a for a in r.assumptions)
    assert any("cargo-heavy" in c for c in r.caveats)
    assert r.data_confidence.level == "High"
    assert r.sources[0].window == "12 months, Aug 2025–Jul 2026"
    assert r.coverage is None


def test_route_mix_anc_sanity_bounds(real_snapshot):
    """Golden sanity bound (SPEC §11): ANC passenger long-haul share within 1–40 %."""
    d = route_mix("ANC").data
    assert 1 <= d.passenger_departures.share_pct <= 40
    assert d.cargo_inclusive_departures.share_pct > d.passenger_departures.share_pct
    assert d.non_passenger_departure_share_pct > 25
    assert len(d.months) == 12


def test_headline_is_always_class_f_and_stated_consistently(fixture_snapshot):
    for include_cargo in (False, True):
        r = route_mix("AAA", include_cargo=include_cargo)
        assert r.data.passenger_departures.share_pct == 9.1
        assert any("Headline share counts scheduled passenger flights (class F)" in a for a in r.assumptions)
    assert any("list all service classes" in a for a in route_mix("AAA", include_cargo=True).assumptions)
