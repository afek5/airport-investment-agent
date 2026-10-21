"""Live Signal clients against a mock transport: parsing, retry, timeout, TTL cache, graceful envelope."""

import httpx
import pytest

from app import live

NAS_XML = """<AIRPORT_STATUS_INFORMATION><Update_Time>Wed Oct 21 18:22:00 2026 GMT</Update_Time>
<Delay_type><Name>Ground Delay Programs</Name><Ground_Delay_List><Ground_Delay><ARPT>BOS</ARPT>
<Reason>runway construction</Reason><Avg>55 minutes</Avg><Max>4 hours and 39 minutes</Max></Ground_Delay>
</Ground_Delay_List></Delay_type>
<Delay_type><Name>Ground Stop Programs</Name><Ground_Stop_List><Program><ARPT>SFO</ARPT><Reason>low ceilings</Reason>
<End_Time>7:45 pm EDT</End_Time></Program></Ground_Stop_List></Delay_type>
<Delay_type><Name>General Arrival/Departure Delay Info</Name><Arrival_Departure_Delay_List><Delay><ARPT>LAS</ARPT>
<Reason>RWY:Maintenance</Reason><Arrival_Departure Type="Departure"><Min>15 minutes</Min><Max>29 minutes</Max>
<Trend>Decreasing</Trend></Arrival_Departure></Delay></Arrival_Departure_Delay_List></Delay_type>
<Delay_type><Name>Airport Closures</Name><Airport_Closure_List><Airport><ARPT>LAX</ARPT>
<Reason>!LAX 05/277 LAX AD AP CLSD TO NON SKED TRANSIENT GA ACFT EXC 24HR PPR</Reason>
<Start>May 27 at 18:26 UTC.</Start><Reopen>May 28 at 16:00 UTC.</Reopen></Airport></Airport_Closure_List></Delay_type>
</AIRPORT_STATUS_INFORMATION>"""

BTS_ROWS = [  # newest first, as the API orders them
    {"year": "2026", "reporting_month": "2026-04-01T00:00:00.000", "total_departures": "15753",
     "total_passengers": "2147010", "total_seats": "2669813", "total_load_factor": "80.4"},
    {"year": "2026", "reporting_month": "2026-03-01T00:00:00.000", "total_departures": "15595",
     "total_passengers": "2187575", "total_seats": "2589387", "total_load_factor": "84.5"},
]

DOT_ROWS = [
    {"year": "2026", "quarter": "1", "airport_1": "JFK", "airport_2": "SFO", "city1": "New York City, NY",
     "city2": "San Francisco, CA", "nsmiles": "2619", "passengers": "3721.388889", "fare": "494.8826961",
     "carrier_lg": "DL", "large_ms": "0.4361274912", "fare_lg": "601.69", "carrier_low": "AS",
     "lf_ms": "0.1605434052", "fare_low": "297.77"},
    {"year": "2026", "quarter": "1", "airport_1": "LAX", "airport_2": "SFO", "city1": "Los Angeles, CA",
     "city2": "San Francisco, CA", "nsmiles": "379", "passengers": "4717.533333", "fare": "172.4575579",
     "carrier_lg": "UA", "large_ms": "0.3348666205", "fare_lg": "197.35", "carrier_low": "WN",
     "lf_ms": "0.1452783705", "fare_low": "149.13"},
    {"year": "2026", "quarter": "1", "airport_1": "SFO", "airport_2": "SEA", "city1": "San Francisco, CA",
     "city2": "Seattle, WA", "nsmiles": "679", "passengers": "2000", "fare": "150", "carrier_lg": "AS",
     "large_ms": "0.5", "fare_lg": "160", "carrier_low": "AS", "lf_ms": "0.5", "fare_low": "160"},
]


@pytest.fixture(autouse=True)
def mock_live(monkeypatch):
    live.clear_cache()
    monkeypatch.setattr(live, "RETRY_DELAY_S", 0)
    hits: list[httpx.Request] = []
    state = {"handler": None}

    def dispatch(request: httpx.Request) -> httpx.Response:
        hits.append(request)
        return state["handler"](request)

    monkeypatch.setattr(live, "transport", httpx.MockTransport(dispatch))
    yield hits, state
    live.clear_cache()


def _ok(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "data.bts.gov":
        return httpx.Response(200, json=BTS_ROWS)
    if host == "data.transportation.gov":
        if request.url.params.get("$select") == "year,quarter":
            return httpx.Response(200, json=[{"year": "2026", "quarter": "1"}])
        return httpx.Response(200, json=DOT_ROWS)
    return httpx.Response(200, text=NAS_XML)


async def test_live_traffic_parses_and_orders_months(mock_live):
    hits, state = mock_live
    state["handler"] = _ok
    r = await live.live_traffic("sfo", months=2)
    assert [(m.year, m.month) for m in r.data.months] == [(2026, 3), (2026, 4)]
    assert r.data.months[-1].passengers == 2147010 and r.data.months[-1].load_factor_pct == 80.4
    assert r.sources[0].as_of == "Apr 2026" and r.sources[0].window == "2 months, Mar 2026–Apr 2026"
    assert r.data_confidence.level == "High"
    assert any("never changes" in c for c in r.caveats)
    assert "origin_airport_code='SFO'" in hits[0].url.params["$where"]


async def test_od_demand_latest_quarter_sorted_and_oriented(mock_live):
    _, state = mock_live
    state["handler"] = _ok
    r = await live.od_demand("SFO", top_n=2)
    d = r.data
    assert (d.year, d.quarter) == (2026, 1)
    assert [m.other_airport for m in d.markets] == ["LAX", "JFK"]  # by passengers/day, the other end of the pair
    assert d.markets[0].passengers_per_day == 4717.5 and d.markets[0].large_ms_pct == 33.5
    assert d.markets[0].fare == 172.46
    assert r.data_confidence.level == "Medium"
    assert r.sources[0].as_of == "2026 Q1"


async def test_live_delays_parses_every_kind_and_filters(mock_live):
    _, state = mock_live
    state["handler"] = _ok
    r = await live.live_delays()
    kinds = {d.iata: d for d in r.data.delays}
    assert kinds["BOS"].kind == "Ground Delay Program" and kinds["BOS"].avg_delay == "55 minutes"
    assert kinds["SFO"].kind == "Ground Stop" and kinds["SFO"].until == "7:45 pm EDT"
    assert kinds["LAS"].kind == "Departure Delay" and kinds["LAS"].min_delay == "15 minutes"
    assert kinds["LAX"].kind == "Closure notice (non-scheduled transient GA only)"
    assert r.data.update_time == "Wed Oct 21 18:22:00 2026 GMT"

    r = await live.live_delays(["LAX", "SNA", "BOS"])
    assert {d.iata for d in r.data.delays} == {"LAX", "BOS"}
    # a GA-only closure notice is not an active delay for airline traffic
    assert r.data.no_active_delay == ["LAX", "SNA"]
    assert any("non-scheduled general aviation" in c for c in r.caveats)


async def test_retry_once_then_succeed(mock_live):
    hits, state = mock_live
    attempts = {"n": 0}

    def flaky(request):
        attempts["n"] += 1
        return httpx.Response(503) if attempts["n"] == 1 else _ok(request)

    state["handler"] = flaky
    r = await live.live_delays(["BOS"])
    assert r.data_confidence.level == "High" and len(hits) == 2


async def test_two_failures_give_the_graceful_envelope(mock_live, real_snapshot):
    hits, state = mock_live

    def timeout(request):
        raise httpx.ReadTimeout("timed out", request=request)

    state["handler"] = timeout
    r = await live.live_traffic("SFO")
    assert len(hits) == 2  # one retry
    assert r.data.months == [] and r.data_confidence.level == "Low"
    assert r.caveats[0] == "live source unavailable; answering from Snapshot as of T-100 Jul 2026"


async def test_ttl_cache_serves_repeat_calls(mock_live, monkeypatch):
    hits, state = mock_live
    state["handler"] = _ok
    await live.live_delays(["BOS"])
    await live.live_delays(["LAX"])
    assert len(hits) == 1
    monkeypatch.setattr(live, "CACHE_TTL_S", 0)
    await live.live_delays(["BOS"])
    assert len(hits) == 2


async def test_airport_codes_are_validated_before_any_query(mock_live):
    hits, state = mock_live
    state["handler"] = _ok
    with pytest.raises(ValueError):
        await live.live_traffic("SFO' OR 1=1 --")
    assert hits == []
    assert (await live.live_traffic("KSFO")).data.iata == "SFO"
