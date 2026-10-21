"""The committed Snapshot meets SPEC §3 and the P1-A done-when (runs on a fresh clone; no raw data needed)."""

import json

import pandas as pd
import pytest

import build_snapshot as bs

OUT = bs.OUT
MANIFEST = json.loads((OUT / "manifest.json").read_text())

REQUIRED = {
    "airports": ["iata", "faa_locid", "icao", "name", "city", "state", "faa_region", "hub_size", "is_primary",
                 "lat", "lon", "cbsa_code", "cbsa_name", "runway_count"],
    "enplanements": ["iata", "cy2024", "cy2025", "yoy_pct"],
    "taf": ["iata", "fiscal_year", "is_forecast", "enplanements_total", "enplanements_international",
            "ops_air_carrier", "ops_itinerant_total"],
    "t100_routes": ["year", "month", "origin", "dest", "dest_country", "service_class", "distance_mi",
                    "departures_performed", "departures_scheduled", "seats", "passengers", "freight_lbs"],
    "ontime_airport_month": ["origin", "year", "month", "flights", "dep_del15_share", "avg_taxi_out_min",
                             "cancel_rate", "nas_delay_min_per_flight", "avg_dep_delay_min"],
    "metro_population": ["cbsa_code", "cbsa_name"] + [f"pop_{y}" for y in range(2020, 2026)],
    "runway_capacity": ["iata", "vfr_arrivals_hr", "ifr_arrivals_hr", "vfr_departures_hr", "ifr_departures_hr",
                        "source_note"],
}


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(OUT / f"{name}.parquet")


@pytest.mark.parametrize("table", sorted(REQUIRED))
def test_every_spec_table_exists_with_its_columns(table):
    df = load(table)
    assert len(df) > 0
    assert not [c for c in REQUIRED[table] if c not in df.columns]
    entry = MANIFEST["tables"][table]
    for key in ("source", "url", "as_of", "window", "rows", "built_at"):
        assert entry.get(key), f"{table} manifest lacks {key}"
    assert entry["rows"] == len(df)


@pytest.mark.parametrize("table", ["t100_routes", "ontime_airport_month"])
def test_manifest_lists_the_actual_months(table):
    df = load(table)
    actual = sorted({f"{y}-{m:02d}" for y, m in zip(df["year"], df["month"])})
    assert MANIFEST["tables"][table]["months"] == actual


def test_t100_covers_24_months_ending_jul_2026():
    months = MANIFEST["tables"]["t100_routes"]["months"]
    assert len(months) == 24 and months[0] == "2024-08" and months[-1] == "2026-07"
    assert MANIFEST["tables"]["t100_routes"]["window"] == "24 months, Aug 2024–Jul 2026"
    df = load("t100_routes")
    assert (df["departures_performed"] > 0).all()
    assert df["dest_country"].notna().all()


def test_ontime_has_at_least_6_months_ending_aug_2026():
    months = MANIFEST["tables"]["ontime_airport_month"]["months"]
    assert len(months) >= 6 and months[-1] == "2026-08"


def test_taf_total_includes_international_sfo_fy2024():
    taf = load("taf")
    sfo = taf[(taf["iata"] == "SFO") & (taf["fiscal_year"] == 2024)].iloc[0]
    assert sfo["enplanements_total"] == 24_765_642          # aac + aat + commuter + us_flag + frgn_flag
    assert sfo["enplanements_total"] != 17_490_518          # the domestic-only sum would be wrong
    assert sfo["enplanements_international"] == 3_093_934 + 4_181_190
    assert not sfo["is_forecast"]
    assert sorted(taf["fiscal_year"].unique()) == list(range(2015, 2046))
    assert taf.loc[taf["is_forecast"], "fiscal_year"].min() == 2025


def test_snapshot_is_at_most_25_mb():
    total = sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    assert total <= 25 * 1024 * 1024


def test_universe_holds_370_primary_airports_incl_new_england():
    a = load("airports")
    assert a["is_primary"].all() and len(a) >= 370
    assert {"BOS", "BDL", "PVD", "MHT", "PWM", "BTV"} <= set(a["iata"])
    assert not a["iata"].duplicated().any()


def test_golden_airports_have_a_cbsa_with_population():
    a = load("airports").set_index("iata")
    pop = load("metro_population").set_index("cbsa_code")["pop_2025"]
    for iata in ["BOS", "BDL", "PVD", "MHT", "PWM", "BTV", "LAX", "SNA", "SFO", "ANC"]:
        assert a.loc[iata, "cbsa_code"] in pop.index, iata
    assert a.loc["LAX", "cbsa_code"] == a.loc["SNA", "cbsa_code"] == "31080"


def test_enplanements_yoy_is_percent():
    e = load("enplanements").set_index("iata")
    assert e.loc["SFO", "cy2025"] == 26_251_850 and e.loc["SFO", "cy2024"] == 25_078_968
    assert e.loc["SFO", "yoy_pct"] == pytest.approx(4.6768, abs=1e-3)


def test_runway_capacity_is_cited_and_ifr_drops():
    rc = load("runway_capacity").set_index("iata")
    assert set(rc.index) == {"SFO", "LAX", "SNA", "BOS"}
    assert rc["source_note"].str.len().gt(40).all() and rc["source_url"].str.startswith("https://www.faa.gov").all()
    assert (rc["ifr_arrivals_hr"] < rc["vfr_arrivals_hr"]).all()
    assert rc.loc["SFO", "ifr_arrival_drop_pct"] == pytest.approx(33.3)


def test_ontime_aug_2026_matches_the_research_sample():
    o = load("ontime_airport_month")
    row = o[(o["origin"] == "SFO") & (o["year"] == 2026) & (o["month"] == 8)].iloc[0]
    assert row["flights"] == 13_560
    assert row["dep_del15_share"] == pytest.approx(0.319, abs=5e-4)
    assert row["avg_taxi_out_min"] == pytest.approx(27.8, abs=0.05)
