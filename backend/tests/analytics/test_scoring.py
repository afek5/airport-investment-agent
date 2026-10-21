"""SPEC §11 layer 1: percentile, median imputation, Coverage/Provisional, not-ranked, geometric mean,
weights, TAF total, determinism — on the hand-made Snapshot in conftest.py."""

import math

import pandas as pd
import pytest

from app import snapshot
from app.analytics import airport_scorecard, rank_airports
from app.analytics.scoring import investment_score, percentile, pillar_score
from app.contracts import RankingData, ScorecardData, ToolResult, Weights

NEW_ENGLAND = ["CT", "ME", "MA", "NH", "RI", "VT"]


# ───────────── pure functions ─────────────

def test_percentile_is_average_rank_times_100_ignoring_nulls():
    s = pd.Series([10.0, None, 30.0, 20.0, 20.0], index=list("abcde"))
    p = percentile(s)
    assert p["a"] == 25.0 and p["c"] == 100.0
    assert p["d"] == p["e"] == 62.5  # ties share the average rank (2.5 / 4)
    assert math.isnan(p["b"])


def test_median_imputation_exact_formula():
    # SPEC §4: Pressure 80/20/20 scores 44; 80/missing/missing scores 62.
    assert pillar_score("pressure", {"load_factor": 80, "delay_share": 20, "taxi_out": 20}) == (pytest.approx(44.0), [])
    score, imputed = pillar_score("pressure", {"load_factor": 80, "delay_share": None, "taxi_out": float("nan")})
    assert score == pytest.approx(62.0)
    assert imputed == ["delay_share", "taxi_out"]


def test_whole_pillar_missing_has_no_score():
    assert pillar_score("momentum", {"forecast_cagr": None, "enpl_yoy": None}) == (None, ["forecast_cagr", "enpl_yoy"])


def test_geometric_mean_penalises_a_weak_pillar_and_floors_at_1():
    w = Weights()
    assert investment_score({"momentum": 50, "pressure": 62, "scale": 80}, w) == pytest.approx(61.287, abs=1e-3)
    # arithmetic mean would be 75.25; the geometric mean punishes the 1
    assert investment_score({"momentum": 100, "pressure": 100, "scale": 1}, w) == pytest.approx(10 ** 1.5)
    assert investment_score({"momentum": 100, "pressure": 100, "scale": 0}, w) == pytest.approx(10 ** 1.5)
    assert investment_score({"momentum": 100, "pressure": 100, "scale": 100}, w) == pytest.approx(100.0)


def test_weights_are_normalised():
    w = Weights(momentum=0.7, pressure=0.4, scale=0.25).normalised()
    assert w.momentum + w.pressure + w.scale == pytest.approx(1.0)
    assert w.momentum == pytest.approx(0.7 / 1.35)
    with pytest.raises(ValueError):
        Weights(momentum=0, pressure=0, scale=0).normalised()


# ───────────── end to end on the fixture Snapshot ─────────────

def _card(iata, **kw):
    return airport_scorecard(iata, **kw).data


def _pct(card: ScorecardData) -> dict[str, float | None]:
    return {m.metric: m.percentile for p in card.pillars for m in p.metrics}


def test_percentiles_on_fixture(scoring_snapshot):
    assert _pct(_card("PWM")) == {
        "forecast_cagr": 80.0, "enpl_yoy": 80.0, "load_factor": 80.0, "delay_share": None, "taxi_out": None,
        "enplanements": 50.0, "metro_pop": 40.0,
    }
    # the non-primary XYZ (LF 99 %) is outside the universe, so SFO's LF is the 100th percentile
    assert _pct(_card("SFO"))["load_factor"] == 100.0


def test_ontime_window_and_thin_coverage(scoring_snapshot):
    raw = {m.metric: m.raw_value for p in _card("BOS").pillars for m in p.metrics}
    # 12 months only: the older Aug 2025 month (95 % delayed, 100,000 flights) is ignored
    assert raw["delay_share"] == 25.0 and raw["taxi_out"] == 20.0
    assert raw["load_factor"] == 70.0  # class F only: the cargo rows' seats are ignored
    # PWM has 900 reporting-carrier departures (< 1,000) → unmeasured
    pwm = {m.metric: m for p in _card("PWM").pillars for m in p.metrics}
    assert pwm["delay_share"].raw_value is None and pwm["delay_share"].imputed


def test_provisional_pwm_pressure_62_with_labels(scoring_snapshot):
    r = airport_scorecard("PWM")
    d = r.data
    pillars = {p.pillar: p.score for p in d.pillars}
    assert pillars == {"momentum": 80.0, "pressure": 62.0, "scale": 47.0}
    expected = math.exp(0.35 * math.log(80) + 0.40 * math.log(62) + 0.25 * math.log(47))
    assert d.score == round(expected, 1)
    assert d.provisional and d.imputed_metrics == ["delay_share", "taxi_out"]
    assert r.coverage.measured == 5 and r.coverage.of == 7
    assert r.data_confidence.level == "Medium"
    assert any("fewer than 1,000 reporting-carrier departures" in x for x in r.data_confidence.reasons)
    assert any("Provisional" in c and "delay_share, taxi_out" in c for c in r.caveats)


def test_full_coverage_is_high_confidence(scoring_snapshot):
    r = airport_scorecard("BOS")
    assert r.coverage.measured == 7 and not r.data.provisional and r.data_confidence.level == "High"


def test_whole_pillar_missing_is_not_ranked(scoring_snapshot):
    r = rank_airports(states=NEW_ENGLAND)
    assert [n.iata for n in r.data.not_ranked] == ["BTV"]
    assert "Demand Momentum" in r.data.not_ranked[0].reason
    assert "BTV" not in [a.iata for a in r.data.ranked]
    card = airport_scorecard("BTV")
    assert card.data.score is None and card.data.national_rank is None
    assert card.data_confidence.level == "Low"  # 3 of 7 measured


def test_ranking_matches_independent_recomputation(scoring_snapshot):
    # Independent recomputation from the table in conftest.py's docstring.
    p = {  # momentum, pressure, scale
        "BOS": (0.6 * 40 + 0.4 * 60, 0.4 * 20 + 0.3 * 80 + 0.3 * 80, 0.7 * 250 / 3 + 0.3 * 100),
        "BDL": (0.6 * 100 + 0.4 * 100, 0.4 * 40 + 0.3 * 40 + 0.3 * 40, 0.7 * 200 / 3 + 0.3 * 60),
        "MHT": (0.6 * 20 + 0.4 * 20, 0.4 * 60 + 0.3 * 20 + 0.3 * 20, 0.7 * 100 / 3 + 0.3 * 20),
        "PWM": (80, 62, 47),
    }
    score = {k: math.exp(0.35 * math.log(m) + 0.4 * math.log(pr) + 0.25 * math.log(s)) for k, (m, pr, s) in p.items()}
    expected_order = sorted(score, key=lambda k: -score[k])
    r = rank_airports(states=NEW_ENGLAND)
    assert [a.iata for a in r.data.ranked] == expected_order
    for a in r.data.ranked:
        assert a.score == round(score[a.iata], 1)
        assert a.pillars.pressure == round(p[a.iata][1], 1)
    pwm = next(a for a in r.data.ranked if a.iata == "PWM")
    assert pwm.provisional and pwm.coverage.measured == 5 and pwm.imputed_metrics == ["delay_share", "taxi_out"]
    assert r.data_confidence.level == "Medium"  # the weakest listed airport (PWM, 5/7) wins
    assert any("PWM 5/7 (imputed delay_share, taxi_out)" in x for x in r.data_confidence.reasons)


def test_ranking_carries_screening_caveat_and_sources(scoring_snapshot):
    r = rank_airports(states=NEW_ENGLAND)
    assert any("screening signal" in c and "does not establish" in c for c in r.caveats)
    tables = {s.name for s in r.sources}
    assert {"fixture airports", "fixture t100_routes", "fixture ontime_airport_month", "fixture taf"} <= tables
    t100 = next(s for s in r.sources if s.name == "fixture t100_routes")
    assert t100.window == "12 months, Aug 2025–Jul 2026" and t100.as_of == "Jul 2026"
    ontime = next(s for s in r.sources if s.name == "fixture ontime_airport_month")
    assert ontime.window == "12 months, Sep 2025–Aug 2026"
    assert r.data.universe_size == 6


def test_scope_filters_and_pillar_ranking(scoring_snapshot):
    assert {a.iata for a in rank_airports(hub_sizes=["large"]).data.ranked} == {"SFO", "BOS"}
    assert rank_airports(hub_sizes=["L"]).data.hub_sizes == ["L"]
    assert {a.iata for a in rank_airports(faa_region="wp").data.ranked} == {"SFO"}
    r = rank_airports(pillar="pressure")
    assert r.data.ranked[0].iata == "SFO"
    assert r.data.ranked[0].score == r.data.ranked[0].pillars.pressure
    assert rank_airports(top_n=2).data.ranked[-1].rank == 2
    with pytest.raises(ValueError):
        rank_airports(hub_sizes=["huge"])


def test_weights_change_the_ranking(scoring_snapshot):
    base = rank_airports(states=NEW_ENGLAND)
    growth = rank_airports(states=NEW_ENGLAND, weights={"momentum": 0.70, "pressure": 0.40, "scale": 0.25})
    assert growth.data.weights.momentum == pytest.approx(0.70 / 1.35, abs=1e-9)
    assert growth.data.ranked[0].iata == "BDL"  # strongest Demand Momentum
    moved = {a.iata: a.score for a in base.data.ranked} != {a.iata: a.score for a in growth.data.ranked}
    assert moved
    assert any("custom" in a for a in growth.assumptions)


def test_scorecard_ranks(scoring_snapshot):
    d = _card("SFO")
    assert d.national_of == 5 and d.hub_of == 2  # ranked: BOS BDL MHT PWM SFO; large hubs: BOS SFO
    assert 1 <= d.national_rank <= 5 and 1 <= d.hub_rank <= 2
    with pytest.raises(ValueError):
        airport_scorecard("XYZ")  # not primary


def test_forecast_cagr_uses_total_including_international(scoring_snapshot):
    raw = {m.metric: m.raw_value for p in _card("SFO").pillars for m in p.metrics}
    assert raw["forecast_cagr"] == round(100 * (1.3 ** (1 / 11) - 1), 1)


def test_determinism_byte_identical(scoring_snapshot):
    a = rank_airports(top_n=100).model_dump_json()
    snapshot.use_snapshot_dir(scoring_snapshot)  # reopen the Snapshot from scratch
    b = rank_airports(top_n=100).model_dump_json()
    assert a == b
    w = {"momentum": 0.7}
    assert rank_airports(weights=w).model_dump_json() == rank_airports(weights=w).model_dump_json()


def test_envelopes_validate(scoring_snapshot):
    for r, model in ((rank_airports(), RankingData), (airport_scorecard("BOS"), ScorecardData)):
        assert isinstance(r.data, model)
        again = ToolResult[model].model_validate_json(r.model_dump_json())
        assert again == r
