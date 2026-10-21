from app.analytics import resolve_airports


def test_la_alias_assumes_lax_and_offers_alternates(fixture_snapshot):
    r = resolve_airports("LA")
    assert r.data.resolved == "LAX"
    assert "BUR" in r.data.alternates and "SNA" in r.data.alternates
    assert any("LA = LAX" in a for a in r.assumptions)


def test_santa_ana_is_sna(fixture_snapshot):
    assert resolve_airports("Santa Ana").data.resolved == "SNA"
    assert resolve_airports("Santa Ana airport").data.resolved == "SNA"


def test_codes_match_iata_and_icao(fixture_snapshot):
    assert resolve_airports("sfo").data.resolved == "SFO"
    r = resolve_airports("KSFO")
    assert r.data.resolved == "SFO" and r.data.candidates[0].match == "code"
    assert r.data_confidence.level == "High"


def test_name_match_is_medium_and_stated(fixture_snapshot):
    r = resolve_airports("Alphaville")
    assert r.data.resolved == "AAA"
    assert r.data_confidence.level == "Medium"
    assert r.assumptions


def test_unknown_returns_none_low(fixture_snapshot):
    r = resolve_airports("Atlantis")
    assert r.data.resolved is None and r.data_confidence.level == "Low"


def test_real_snapshot_anchorage(real_snapshot):
    assert resolve_airports("Anchorage").data.resolved == "ANC"
