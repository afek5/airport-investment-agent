"""query_public_api offline: whitelist, SoQL input guards, limit clamping, envelope, error paths (mock transport)."""

import httpx
import pytest
from pydantic_ai.messages import ModelRequest, RetryPromptPart, ToolReturnPart

from app import live
from app.agent import agent
from app.contracts import PublicApiData, ToolResult
from app.live import public_api
from tests.agent.scripted import _model

FARES = [  # newest first, numbers as Socrata returns them (strings)
    {"year": "2026", "quarter": "1", "avg_fare": "345.5884471", "pax": "2425.74"},
    {"year": "2025", "quarter": "4", "avg_fare": "375.6972896", "pax": "2957.2"},
    {"year": "2025", "quarter": "3", "avg_fare": "361.8235193", "pax": "3105.03"},
]


@pytest.fixture(autouse=True)
def mock_live(monkeypatch):
    live.clear_cache()
    monkeypatch.setattr(live, "RETRY_DELAY_S", 0)
    hits: list[httpx.Request] = []
    state = {"handler": lambda request: httpx.Response(200, json=FARES)}

    def dispatch(request: httpx.Request) -> httpx.Response:
        hits.append(request)
        return state["handler"](request)

    monkeypatch.setattr(live, "transport", httpx.MockTransport(dispatch))
    yield hits, state
    live.clear_cache()


# ───────────────────────────── whitelist ─────────────────────────────


def test_whitelist_is_exactly_the_three_spec_datasets():
    assert {k: (d.resource_id, d.url) for k, d in public_api.PUBLIC_DATASETS.items()} == {
        "bts_airport_month": ("r495-tyji", "https://data.bts.gov/resource/r495-tyji.json"),
        "dot_airfare_pairs": ("tfrh-tu9e", "https://data.transportation.gov/resource/tfrh-tu9e.json"),
        "dot_airfare_city_pairs": ("yj5y-b2ir", "https://data.transportation.gov/resource/yj5y-b2ir.json"),
    }


@pytest.mark.parametrize("dataset", ["t100_routes", "r495-tyji", "https://evil.example/resource/x.json", "", None])
async def test_unknown_dataset_is_rejected_before_any_request(mock_live, dataset):
    hits, _ = mock_live
    with pytest.raises(ValueError, match="unknown dataset"):
        await live.query_public_api(dataset)
    assert hits == []


async def test_request_goes_only_to_the_whitelisted_endpoint(mock_live):
    hits, _ = mock_live
    for key, ds in public_api.PUBLIC_DATASETS.items():
        await live.query_public_api(key, limit=3)
        req = hits[-1]
        assert str(req.url).split("?")[0] == ds.url
        assert set(req.url.params) == {"$select", "$limit"}
        assert req.url.params["$select"] == ds.default_select  # curated columns, no point/geocode blobs


# ───────────────────────────── input guards ─────────────────────────────


@pytest.mark.parametrize("field,value", [
    ("where", "airport_1='BOS'&$limit=100000"),
    ("where", "airport_1='BOS' AND $where=1=1"),
    ("select", "year,$$app_token"),
    ("order", "year; DROP"),
    ("where", "airport_1='BOS' |> SELECT *"),
    ("group", "year#"),
    ("where", "airport_1='BOS'\n$limit=9"),
    ("where", "x" * 1001),
])
async def test_soql_injection_and_oversized_clauses_are_rejected(mock_live, field, value):
    hits, _ = mock_live
    with pytest.raises(ValueError):
        await live.query_public_api("dot_airfare_pairs", **{field: value})
    assert hits == []


async def test_group_needs_an_explicit_select(mock_live):
    with pytest.raises(ValueError, match="explicit select"):
        await live.query_public_api("dot_airfare_pairs", group="year,quarter")


async def test_clauses_pass_through_url_encoded_as_separate_params(mock_live):
    hits, _ = mock_live
    await live.query_public_api("dot_airfare_pairs", select=" year,quarter,avg(fare) AS avg_fare ",
                                where="(airport_1='BOS' AND airport_2='LAX') OR (airport_1='LAX' AND airport_2='BOS')",
                                group="year,quarter", order="year DESC,quarter DESC", limit=8)
    p = hits[0].url.params
    assert p["$select"] == "year,quarter,avg(fare) AS avg_fare"
    assert p["$where"] == "(airport_1='BOS' AND airport_2='LAX') OR (airport_1='LAX' AND airport_2='BOS')"
    assert p["$group"] == "year,quarter" and p["$order"] == "year DESC,quarter DESC"
    assert p["$limit"] == "9"  # limit + 1, to detect truncation exactly


# ───────────────────────────── limit clamping ─────────────────────────────


@pytest.mark.parametrize("given,clamped", [(0, 1), (-5, 1), (1, 1), (500, 500), (501, 500), (10_000, 500),
                                           ("50", 50), (None, 100), ("lots", 100)])
def test_limit_is_clamped_to_1_to_500(given, clamped):
    assert public_api.clamp_limit(given) == clamped


async def test_huge_limit_requests_at_most_501_rows(mock_live):
    hits, _ = mock_live
    r = await live.query_public_api("bts_airport_month", limit=99_999)
    assert hits[0].url.params["$limit"] == "501" and r.data.limit == 500
    assert r.data.sql.endswith("$limit=500")


async def test_truncation_is_flagged_when_more_rows_match(mock_live):
    r = await live.query_public_api("dot_airfare_pairs", select="year,quarter,avg_fare,pax", limit=2)
    assert r.data.row_count == 2 and r.data.truncated
    assert any("first 2 rows" in a for a in r.assumptions)
    r = await live.query_public_api("dot_airfare_pairs", select="year,quarter,avg_fare,pax", limit=3)
    assert r.data.row_count == 3 and not r.data.truncated


# ───────────────────────────── envelope ─────────────────────────────


async def test_envelope_is_ad_hoc_medium_with_typed_rows_and_period(mock_live):
    r = await live.query_public_api("dot_airfare_pairs", select="year,quarter,avg(fare) AS avg_fare,sum(passengers) AS pax",
                                    where="airport_1='BOS' AND airport_2='LAX'", group="year,quarter",
                                    order="year DESC,quarter DESC")
    assert isinstance(r.data, PublicApiData)
    assert r.ad_hoc is True
    assert r.data_confidence.level == "Medium"
    assert "ad-hoc query outside the scoring methodology" in r.data_confidence.reasons
    assert r.data.dataset == "dot_airfare_pairs" and r.data.resource_id == "tfrh-tu9e"
    assert r.data.columns == ["year", "quarter", "avg_fare", "pax"]
    assert r.data.rows[0] == [2026, 1, 345.59, 2425.74]  # numbers typed and rounded by the tool, not the LLM
    assert r.data.sql.splitlines() == ["$select=year,quarter,avg(fare) AS avg_fare,sum(passengers) AS pax",
                                       "$where=airport_1='BOS' AND airport_2='LAX'", "$group=year,quarter",
                                       "$order=year DESC,quarter DESC", "$limit=100"]
    src = r.sources[0]
    assert src.url == "https://data.transportation.gov/resource/tfrh-tu9e.json"
    assert src.as_of == "2026 Q1" and src.window == "3 quarters, 2025 Q3–2026 Q1"
    assert r.data.row_count == 3 and r.data.period_count == 3 and r.data.periods == "3 quarters, 2025 Q3–2026 Q1"
    assert "One row is one group of the query's GROUP BY columns (year,quarter). The result has 3 rows covering " \
           "3 distinct quarters (2025 Q3–2026 Q1): one row per quarter." in r.assumptions
    assert any("never changes an Investment Opportunity Score" in c for c in r.caveats)
    assert any("DB1B 10% ticket sample" in c for c in r.caveats)
    # round-trips through the SPEC §5 envelope
    back = ToolResult[PublicApiData].model_validate_json(r.model_dump_json())
    assert back.data.rows == r.data.rows and back.ad_hoc


async def test_identifiers_stay_text_and_months_give_the_period(mock_live):
    _, state = mock_live
    rows = [{"origin_airport_id": "10721", "origin_airport_code": "BOS", "year": "2026",
             "reporting_month": "2026-04-01T00:00:00.000", "total_passengers": "1841463", "total_load_factor": "79.6"},
            {"origin_airport_id": "10721", "origin_airport_code": "BOS", "year": "2026",
             "reporting_month": "2026-03-01T00:00:00.000", "total_passengers": "1670139", "total_load_factor": "79"}]
    state["handler"] = lambda request: httpx.Response(200, json=rows)
    r = await live.query_public_api("bts_airport_month", select="*", where="origin_airport_code='BOS'")
    row = dict(zip(r.data.columns, r.data.rows[0]))
    assert row["origin_airport_id"] == "10721" and row["year"] == 2026
    assert row["total_passengers"] == 1841463 and row["total_load_factor"] == 79.6
    assert r.sources[0].as_of == "Apr 2026" and r.sources[0].window == "2 months, Mar 2026–Apr 2026"


async def test_no_rows_is_low_confidence_and_still_ad_hoc(mock_live):
    _, state = mock_live
    state["handler"] = lambda request: httpx.Response(200, json=[])
    r = await live.query_public_api("dot_airfare_city_pairs", where="city1='Nowhere'")
    assert r.data.rows == [] and r.ad_hoc and r.data_confidence.level == "Low"


# ───────────────────────────── error paths ─────────────────────────────


async def test_outage_retries_once_then_returns_the_graceful_envelope(mock_live, real_snapshot):
    hits, state = mock_live

    def timeout(request):
        raise httpx.ReadTimeout("timed out", request=request)

    state["handler"] = timeout
    r = await live.query_public_api("bts_airport_month", where="origin_airport_code='BOS'")
    assert len(hits) == 2  # one retry
    assert r.ad_hoc and r.data.rows == [] and r.data_confidence.level == "Low"
    assert r.caveats[0] == "live source unavailable; answering from Snapshot as of T-100 Jul 2026"
    assert r.sources[0].as_of == "unavailable"


async def test_soql_error_is_not_retried_and_goes_back_as_a_value_error(mock_live):
    hits, state = mock_live
    state["handler"] = lambda request: httpx.Response(400, json={
        "message": "Query coordinator error: query.soql.no-such-column; No such column: airport_1; position: x",
        "errorCode": "query.soql.no-such-column"})
    with pytest.raises(ValueError, match="No such column: airport_1"):
        await live.query_public_api("dot_airfare_city_pairs", where="airport_1='BOS'")
    assert len(hits) == 1


async def test_ttl_cache_serves_the_repeat_query(mock_live):
    hits, _ = mock_live
    a = await live.query_public_api("dot_airfare_pairs", select="year,quarter,avg_fare,pax")
    b = await live.query_public_api("dot_airfare_pairs", select="year,quarter,avg_fare,pax")
    assert len(hits) == 1 and a.data.rows == b.data.rows


async def test_agent_sends_bad_soql_back_to_the_model_as_a_retry(mock_live):
    """Through the registered tool: an injection attempt never reaches the network and the model is asked to fix it."""
    hits, _ = mock_live

    def step(messages, info):
        retried = any(isinstance(p, RetryPromptPart) for m in messages if isinstance(m, ModelRequest) for p in m.parts)
        returned = any(isinstance(p, ToolReturnPart) for m in messages if isinstance(m, ModelRequest) for p in m.parts)
        if returned:
            return "text", "done"
        args = {"dataset": "dot_airfare_pairs", "select": "year,quarter,avg_fare,pax"}
        if not retried:
            args["where"] = "airport_1='BOS'&$limit=99999"
        return "tool", {"name": "query_public_api", "args": args}

    with agent.override(model=_model(step)):
        result = await agent.run("average fare BOS-LAX by quarter")
    retries = [p for m in result.all_messages() if isinstance(m, ModelRequest) for p in m.parts
               if isinstance(p, RetryPromptPart)]
    assert retries and "not allowed" in str(retries[0].content)
    assert len(hits) == 1 and "$where" not in hits[0].url.params
    out = next(p.content for m in result.all_messages() if isinstance(m, ModelRequest) for p in m.parts
               if isinstance(p, ToolReturnPart))
    assert out.ad_hoc and out.data.rows[0][2] == 345.59


# ───────────────────────────── counts: rows vs periods ─────────────────────────────


def _quarters(first: tuple[int, int], n: int) -> list[tuple[int, int]]:
    y, q = first
    out = []
    for _ in range(n):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


async def test_100_quarter_rows_state_100_rows_and_100_quarters(mock_live):
    # The live answer once said "Window returned: 100 quarters" for 100 rows; the tool states both counts.
    _, state = mock_live
    rows = [{"year": str(y), "quarter": str(q), "avg_fare": "300.5"} for y, q in reversed(_quarters((2001, 2), 100))]
    state["handler"] = lambda request: httpx.Response(200, json=rows)
    r = await live.query_public_api("dot_airfare_pairs", select="year,quarter,avg(fare) AS avg_fare",
                                    group="year,quarter", order="year DESC,quarter DESC", limit=100)
    assert r.data.row_count == 100 and r.data.period_count == 100
    assert r.data.periods == "100 quarters, 2001 Q2–2026 Q1"
    assert any(a.endswith("The result has 100 rows covering 100 distinct quarters (2001 Q2–2026 Q1): one row per "
                          "quarter.") for a in r.assumptions)


async def test_several_rows_per_quarter_are_not_called_quarters(mock_live):
    _, state = mock_live
    rows = [{"year": "2025", "quarter": str(q), "carrier_lg": c, "fare": "300"} for q in (3, 4) for c in ("AA", "B6", "DL")]
    state["handler"] = lambda request: httpx.Response(200, json=rows)
    r = await live.query_public_api("dot_airfare_pairs", select="year,quarter,carrier_lg,fare",
                                    where="airport_1='BOS'")
    assert r.data.row_count == 6 and r.data.period_count == 2 and r.data.periods == "2 quarters, 2025 Q3–2025 Q4"
    line = next(a for a in r.assumptions if a.startswith("One row is"))
    assert line == ("One row is one airport-pair market in one quarter (Table 1a record). The result has 6 rows "
                    "covering 2 distinct quarters (2025 Q3–2025 Q4), so one quarter can span several rows; count "
                    "quarters from `periods`, rows from `row_count`.")


async def test_months_and_no_period_columns(mock_live):
    _, state = mock_live
    rows = [{"origin_airport_code": "BOS", "reporting_month": f"2026-0{m}-01T00:00:00.000", "total_departures": "9000"}
            for m in (3, 4)]
    state["handler"] = lambda request: httpx.Response(200, json=rows)
    r = await live.query_public_api("bts_airport_month", select="origin_airport_code,reporting_month,total_departures")
    assert r.data.period_count == 2 and r.data.periods == "2 months, Mar 2026–Apr 2026"
    assert any(a.startswith("One row is one origin airport in one month") for a in r.assumptions)

    state["handler"] = lambda request: httpx.Response(200, json=[{"avg_fare": "312.4"}])
    r = await live.query_public_api("dot_airfare_pairs", select="avg(fare) AS avg_fare")
    assert r.data.row_count == 1 and r.data.period_count is None and r.data.periods is None
    assert "One row is one aggregate over every matching record. The result has 1 row and no period columns, so " \
           "it states no period count." in r.assumptions
