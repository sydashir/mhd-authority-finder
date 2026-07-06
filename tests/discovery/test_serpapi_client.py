"""Unit tests for the SerpAPI client: cache, billing counters, retry. No network."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from authority_finder.discovery.serpapi_client import (
    QuotaExceededError,
    SerpApiClient,
    SerpApiError,
)

PAYLOAD = {"organic_results": [{"position": 1, "title": "t", "link": "https://x.gov/"}]}


def _client(handler: httpx.MockTransport, cache_dir: Path) -> SerpApiClient:
    return SerpApiClient(
        client=httpx.AsyncClient(transport=handler),
        api_key=SecretStr("test-key"),
        cache_dir=cache_dir,
    )


async def test_max_billed_circuit_breaker_raises(tmp_path: Path) -> None:
    # The (max_billed+1)-th billed search raises BEFORE spending; the cap is never exceeded.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    client = SerpApiClient(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        api_key=SecretStr("k"),
        cache_dir=tmp_path,
        max_billed=2,
    )
    await client.search("q1")
    await client.search("q2")
    with pytest.raises(QuotaExceededError):
        await client.search("q3")
    assert client.billed_search_count == 2  # never overspent past the cap


async def test_cache_miss_then_hit(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["api_key"] == "test-key"
        return httpx.Response(200, json=PAYLOAD)

    client = _client(httpx.MockTransport(handler), tmp_path)
    first = await client.search("maryland health site:.gov")
    second = await client.search("maryland health site:.gov")

    assert calls == 1
    assert first.billed and not second.billed
    assert first.data == second.data == PAYLOAD
    assert client.billed_search_count == 1
    assert client.cache_hit_count == 1


async def test_distinct_queries_get_distinct_cache_entries(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    client = _client(httpx.MockTransport(handler), tmp_path)
    await client.search("query one")
    await client.search("query two")

    assert client.billed_search_count == 2
    assert len(list(tmp_path.glob("*.json"))) == 2


async def test_cached_files_never_contain_the_api_key(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    client = _client(httpx.MockTransport(handler), tmp_path)
    await client.search("query")
    for path in tmp_path.glob("*.json"):
        assert "test-key" not in path.read_text()


async def test_corrupt_cache_entry_is_a_miss(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    client = _client(httpx.MockTransport(handler), tmp_path)
    await client.search("query")
    cache_file = next(tmp_path.glob("*.json"))
    cache_file.write_text("{truncated")

    refetched = await client.search("query")
    assert refetched.billed
    assert json.loads(cache_file.read_text()) == PAYLOAD


async def test_retries_on_429_honoring_retry_after(tmp_path: Path) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=PAYLOAD)

    client = _client(httpx.MockTransport(handler), tmp_path)
    result = await client.search("query")

    assert calls == 2
    assert result.billed
    assert client.billed_search_count == 1


async def test_serpapi_error_payload_raises(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "Invalid API key"})

    client = _client(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(SerpApiError, match="Invalid API key"):
        await client.search("query")
    assert client.billed_search_count == 0
    assert list(tmp_path.glob("*.json")) == []


async def test_no_results_payload_is_empty_not_error(tmp_path: Path) -> None:
    # Live S19: a genuinely-empty search (rural geo + site:.gov filter) returns HTTP 200
    # with SerpAPI's "hasn't returned any results" message — a valid empty set, not a
    # failure. It must NOT raise, must NOT bill (SerpAPI doesn't bill no-results), and
    # must be cached so re-runs of the geo don't re-issue the live call.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": "Google Light hasn't returned any results for this query."}
        )

    client = _client(httpx.MockTransport(handler), tmp_path)
    result = await client.search("wyoming substance abuse site:.gov")
    assert result.billed is False
    assert client.billed_search_count == 0
    assert result.data.get("organic_results", []) == []
    assert list(tmp_path.glob("*.json"))  # cached → future runs skip the live call


async def test_bad_request_raises_without_retry(tmp_path: Path) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "engine gone"})

    client = _client(httpx.MockTransport(handler), tmp_path)
    with pytest.raises(SerpApiError):
        await client.search("query")
    assert calls == 1
