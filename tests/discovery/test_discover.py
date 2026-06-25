"""Orchestrator tests against the real Step-2 fixture. No network, no billing."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from authority_finder.discovery.discover import (
    discover_for_geo,
    discover_many,
    parse_organic_results,
)
from authority_finder.discovery.serpapi_client import QuotaExceededError, SerpApiClient
from authority_finder.geo_monitor.models import GeoPage

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "google_light_california.json"
FIXTURE: dict[str, Any] = json.loads(FIXTURE_PATH.read_text())

CALIFORNIA = GeoPage(
    url="https://inpatientmentalhealthfinder.com/serving/california/",
    site_id="mhd",
    state="california",
    county=None,
    city=None,
    level="state",
    first_seen=datetime.now(UTC),
)


def test_parse_organic_results_full_fixture() -> None:
    results = parse_organic_results(FIXTURE, query="q")
    assert len(results) == 10
    assert [r.position for r in results] == list(range(1, 11))
    assert str(results[0].link) == "https://www.mentalhealth.ca.gov/"
    assert all(r.source_query == "q" for r in results)
    assert all(r.title and r.snippet for r in results)


def test_parse_organic_results_skips_malformed_rows() -> None:
    data = {"organic_results": [{"title": "no link or position"}, *FIXTURE["organic_results"]]}
    assert len(parse_organic_results(data, query="q")) == 10


def test_parse_organic_results_empty_payload() -> None:
    assert parse_organic_results({}, query="q") == []


async def test_discover_many_reraises_quota_exceeded(tmp_path: Path) -> None:
    # max_billed=0 → the first billed search raises QuotaExceededError (NOT a SerpApiError, so
    # discover_for_geo doesn't swallow it); discover_many re-raises so the run aborts loudly
    # instead of silently returning empty results.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic_results": []})

    client = SerpApiClient(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        api_key=SecretStr("k"),
        cache_dir=tmp_path,
        max_billed=0,
    )
    with pytest.raises(QuotaExceededError):
        await discover_many([CALIFORNIA], client=client)


def _serp_client(handler: httpx.MockTransport, cache_dir: Path) -> SerpApiClient:
    return SerpApiClient(
        client=httpx.AsyncClient(transport=handler),
        api_key=SecretStr("test-key"),
        cache_dir=cache_dir,
    )


async def test_discover_for_geo_end_to_end(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=FIXTURE)

    client = _serp_client(httpx.MockTransport(handler), tmp_path)
    result = await discover_for_geo(CALIFORNIA, client=client)

    assert result.queries_run == 4
    assert result.billed_searches == 4
    assert result.errors == []
    assert result.geo.state == "california"
    # Fixture has 10 organic results: 9 distinct .gov orgs + UCLA. The two
    # ca.gov agencies stay separate thanks to the state-portal dedupe key.
    assert len(result.candidates) == 10
    assert result.counts_by_class == {"gov": 9, "edu": 1, "us_local": 0, "other": 0}
    domains = {c.registrable_domain for c in result.candidates}
    assert {"mentalhealth.ca.gov", "dhcs.ca.gov", "ucla.edu", "lacounty.gov"} <= domains
    assert all(len(c.source_queries) == 4 for c in result.candidates)


async def test_discover_for_geo_isolates_query_failures(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "substance" in str(request.url):
            return httpx.Response(400, json={"error": "boom"})
        return httpx.Response(200, json=FIXTURE)

    client = _serp_client(httpx.MockTransport(handler), tmp_path)
    result = await discover_for_geo(CALIFORNIA, client=client)

    assert result.queries_run == 4
    assert result.billed_searches == 3
    assert len(result.errors) == 1
    assert "substance" in result.errors[0].query
    assert len(result.candidates) == 10


async def test_discover_many_isolates_geo_failures(tmp_path: Path) -> None:
    broken = CALIFORNIA.model_copy(update={"county": None, "city": None, "level": "county"})

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=FIXTURE)

    client = _serp_client(httpx.MockTransport(handler), tmp_path)
    results = await discover_many([CALIFORNIA, broken], client=client)

    assert len(results) == 2
    ok, failed = results
    assert len(ok.candidates) == 10
    assert failed.candidates == []
    assert failed.errors and "county-level geo" in failed.errors[0].message
