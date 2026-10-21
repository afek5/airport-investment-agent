"""Golden tool tests G1–G4 (SPEC §11 layer 2): each tool's output on the real Snapshot matches an
independent pandas recomputation (tests/e2e/recompute.py), plus sanity bounds."""

from __future__ import annotations

import pytest

from app import analytics, snapshot
from app.analytics.constants import SCREENING_CAVEAT

from . import recompute as rc
from .recompute import close

pytestmark = pytest.mark.skipif(not (rc.SNAPSHOT / "t100_routes.parquet").exists(), reason="Snapshot not built")


@pytest.fixture(autouse=True)
def real_snapshot():
    snapshot.use_snapshot_dir(rc.SNAPSHOT)
    yield


# ───────────────────────── G1: New England Ranking ─────────────────────────


def test_g1_new_england_ranking_matches_recomputation():
    r = analytics.rank_airports(states=rc.NEW_ENGLAND, top_n=50)
    expected = rc.ranking(rc.NEW_ENGLAND)
    got = [(a.iata, a.score) for a in r.data.ranked]

    assert len(got) >= 5, "G1 needs a ranked table of at least 5 New England Primary Airports"
    assert [i for i, _ in got] == [i for i, _ in expected], "ranking order differs from the recomputation"
    for (iata, score), (_, exp) in zip(got, expected):
        assert close(score, exp), f"{iata}: tool {score} vs recomputed {exp:.3f}"

    full = rc.scores()
    for a in r.data.ranked:
        assert a.coverage.measured == full.at[a.iata, "measured"], a.iata
        assert a.provisional == (a.coverage.measured < 7)
        assert len(a.imputed_metrics) == 7 - a.coverage.measured
        for p in rc.PILLARS:
            assert close(getattr(a.pillars, p), full.at[a.iata, p]), (a.iata, p)


def test_g1_envelope_carries_caveat_confidence_and_as_of():
    r = analytics.rank_airports(states=rc.NEW_ENGLAND)
    assert SCREENING_CAVEAT in r.caveats
    assert r.data_confidence.level in ("High", "Medium", "Low") and r.data_confidence.reasons
    assert r.sources and all(s.as_of for s in r.sources)
    # Provisional scores are disclosed with their imputed metrics in the confidence reasons.
    for a in r.data.ranked:
        if a.provisional:
            assert any(a.iata in reason for reason in r.data_confidence.reasons), a.iata
    # The universe matches the FAA primary list.
    assert r.data.universe_size == len(rc.universe())


def test_g5_growth_twice_as_much_matches_recomputation():
    """G5: "What if growth matters twice as much?" = Demand Momentum weight doubled (0.70, others default)."""
    w = {"momentum": 0.70, "pressure": 0.40, "scale": 0.25}
    r = analytics.rank_airports(states=rc.NEW_ENGLAND, weights=w, top_n=50)
    expected = rc.ranking(rc.NEW_ENGLAND, w)
    assert [a.iata for a in r.data.ranked] == [i for i, _ in expected]
    for a, (_, exp) in zip(r.data.ranked, expected):
        assert close(a.score, exp), a.iata
    assert close(r.data.weights.momentum, 0.70 / 1.35, 1e-3)
    # The changed weights move the ranking (otherwise G5 has nothing to report).
    default = [a.iata for a in analytics.rank_airports(states=rc.NEW_ENGLAND, top_n=50).data.ranked]
    assert default != [a.iata for a in r.data.ranked]


# ───────────────────────── G2: LA vs Santa Ana congestion ─────────────────────────


def test_g2_resolve_la_and_santa_ana():
    la = analytics.resolve_airports("LA")
    assert la.data.resolved == "LAX"
    assert {"BUR", "LGB", "ONT", "SNA"} <= set(la.data.alternates), "LA must offer the alternate airports"
    assert any("LA = LAX" in a for a in la.assumptions)
    assert analytics.resolve_airports("Santa Ana").data.resolved == "SNA"


def test_g2_congestion_compare_matches_recomputation():
    r = analytics.compare_airports(["LAX", "SNA"], lens="congestion")
    exp = rc.congestion(["LAX", "SNA"])
    metrics = {m.key: m for m in r.data.metrics}
    for key in ("delay_share", "taxi_out", "cancel_rate", "nas_delay_min_per_flight", "monthly_departures",
                "deps_per_runway_day", "load_factor"):
        for c in ("LAX", "SNA"):
            value, percentile = exp[key][c]
            assert close(metrics[key].values[c], value), (key, c, metrics[key].values[c], value)
            assert close(metrics[key].percentiles[c], percentile), (key, c, "percentile")
    for c in ("LAX", "SNA"):
        assert close(r.data.congestion_index[c], exp["congestion_index"][c][0]), c
    # Sanity: shares are percents (not fractions) and taxi-out is in minutes.
    assert all(5 < v < 50 for v in metrics["delay_share"].values.values())
    assert all(5 < v < 40 for v in metrics["taxi_out"].values.values())
    assert any("not the Investment Opportunity Score" in a for a in r.assumptions)


# ───────────────────────── G3: Anchorage Long-haul share ─────────────────────────


def test_g3_anchorage_route_mix_matches_recomputation():
    r = analytics.route_mix("ANC")
    d = r.data
    exp = rc.route_mix("ANC")
    for field, key in (("passenger_departures", "passenger_departures"), ("passenger_weighted", "passenger_weighted"),
                       ("cargo_inclusive_departures", "cargo_inclusive"), ("all_cargo_departures", "all_cargo")):
        share = getattr(d, field)
        assert (share.long_haul, share.total, share.share_pct) == exp[key], field
    assert d.non_passenger_departure_share_pct == exp["non_passenger_share"]
    assert [x.dest for x in d.top_long_haul_destinations] == exp["top_destinations"]
    assert d.min_miles == 3000 and len(d.months) == 12


def test_g3_anchorage_sanity_bounds_and_cargo_hub_story():
    d = analytics.route_mix("ANC").data
    assert 1 <= d.passenger_departures.share_pct <= 40, "SPEC §11: ANC passenger long-haul share within 1–40%"
    # The cargo-hub story: the cargo-inclusive share is far above the passenger share.
    assert d.cargo_inclusive_departures.share_pct > 3 * d.passenger_departures.share_pct
    assert d.all_cargo_share_of_long_haul_pct > 50
    caveats = analytics.route_mix("ANC").caveats
    assert any("cargo-heavy" in c for c in caveats)


# ───────────────────────── G4: SFO Unmet Demand ─────────────────────────


def test_g4_sfo_unmet_demand_matches_recomputation():
    r = analytics.unmet_demand("SFO")
    d = r.data
    exp = rc.unmet("SFO")
    ev = {e.key: e for e in d.constraint_evidence}
    for key in ("delay_share", "taxi_out", "nas_delay_min_per_flight", "full_route_month_share"):
        value, median = exp[key]
        assert close(ev[key].value, value), (key, ev[key].value, value)
        assert close(ev[key].benchmark, median), (key, "median", ev[key].benchmark, median)
    assert close(ev["ifr_arrival_drop"].value, exp["ifr_arrival_drop"])
    assert ev["ifr_arrival_drop"].as_of == "2019", "SFO's capacity rates come from the 2019 profile edition"

    g, eg = d.forecast_gap, exp["forecast_gap"]
    assert g.from_fy == 2024 and g.to_fy == 2030
    assert g.enplanements_from == eg["enplanements_from"] == 24_765_642  # TAF total incl. international
    assert g.enplanements_to == eg["enplanements_to"]
    assert close(g.enplanements_pct, eg["enplanements_pct"])
    assert (g.ops_from, g.ops_to) == (eg["ops_from"], eg["ops_to"])
    assert close(g.ops_pct, eg["ops_pct"])

    assert (d.spill_scenario.low, d.spill_scenario.high) == exp["spill"]


def test_g4_sfo_unmet_demand_labels_and_order():
    r = analytics.unmet_demand("SFO")
    d = r.data
    assert r.data_confidence.level == "Medium"
    assert "not calibrated" in d.spill_scenario.label
    assert len(d.cannot_determine) == 5
    assert d.why_drivers and all("Spill" not in w for w in d.why_drivers), "drivers come from observed evidence only"
    assert any("IFR" in e.label for e in d.constraint_evidence), "the IFR vs VFR drop is part of the evidence"
    assert 0 < d.spill_scenario.low < d.spill_scenario.high
