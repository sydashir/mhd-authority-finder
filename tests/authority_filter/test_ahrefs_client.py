"""Ahrefs client behaviour. Zero live calls — every test uses a stub transport or the cache."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from authority_finder.authority_filter.ahrefs_client import (
    BATCH_LIMIT,
    AhrefsClient,
    AhrefsQuotaExceededError,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "ahrefs_batch_orgs.json"


def _fixture_payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def _transport(payload: dict[str, Any], *, calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json=payload,
            headers={"x-api-units-cost-total": "60", "x-api-rows": "20"},
        )

    return httpx.MockTransport(handler)


def _client(transport: httpx.MockTransport, cache_dir: Path, **kw: Any) -> AhrefsClient:
    return AhrefsClient(
        SecretStr("test-key-never-real"),
        cache_dir=cache_dir,
        http_client=httpx.AsyncClient(transport=transport),
        **kw,
    )


@pytest.mark.asyncio
async def test_parses_nested_float_dr_and_strips_trailing_slash(tmp_path: Path) -> None:
    """The live API nests DR one level deep and returns ``url`` with a trailing slash."""
    calls: list[httpx.Request] = []
    client = _client(_transport(_fixture_payload(), calls=calls), tmp_path)

    ratings = await client.domain_ratings(["ncala.org", "nami.org"])

    assert ratings["ncala.org"].dr == 34.0
    assert ratings["nami.org"].dr == 90.0
    # keyed by bare domain, not "ncala.org/"
    assert all("/" not in domain for domain in ratings)


@pytest.mark.asyncio
async def test_sends_required_protocol_field(tmp_path: Path) -> None:
    """Omitting ``protocol`` makes the live API 400 — the client must always send it."""
    calls: list[httpx.Request] = []
    client = _client(_transport(_fixture_payload(), calls=calls), tmp_path)

    await client.domain_ratings(["ncala.org"])

    body = json.loads(calls[0].content)
    assert body["targets"][0]["protocol"] == "both"
    assert body["targets"][0]["mode"] == "domain"
    assert "domain_rating" in body["select"]


@pytest.mark.asyncio
async def test_never_puts_the_key_in_the_body_or_url(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    client = _client(_transport(_fixture_payload(), calls=calls), tmp_path)

    await client.domain_ratings(["ncala.org"])

    request = calls[0]
    assert "test-key-never-real" not in str(request.url)
    assert b"test-key-never-real" not in request.content
    assert request.headers["Authorization"] == "Bearer test-key-never-real"


@pytest.mark.asyncio
async def test_cache_hit_costs_zero_network_calls(tmp_path: Path) -> None:
    """A re-run must be free — the whole point of the ADR-005 disk cache."""
    calls: list[httpx.Request] = []
    payload = _fixture_payload()

    first = _client(_transport(payload, calls=calls), tmp_path)
    await first.domain_ratings(["ncala.org", "nami.org"])
    assert len(calls) == 1

    second = _client(_transport(payload, calls=calls), tmp_path)
    ratings = await second.domain_ratings(["ncala.org", "nami.org"])

    assert len(calls) == 1, "second run must not hit the network"
    assert second.call_count == 0
    assert second.cache_hit_count == 2
    assert ratings["ncala.org"].dr == 34.0


@pytest.mark.asyncio
async def test_tracks_real_units_from_response_headers(tmp_path: Path) -> None:
    """Spend is read from x-api-units-cost-total, never estimated."""
    calls: list[httpx.Request] = []
    client = _client(_transport(_fixture_payload(), calls=calls), tmp_path)

    await client.domain_ratings(["ncala.org"])

    assert client.units_spent == 60
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_batches_at_the_api_limit(tmp_path: Path) -> None:
    """100 targets per call is the documented ceiling; batching is ~17x cheaper per domain."""
    calls: list[httpx.Request] = []
    domains = [f"org{n}.org" for n in range(BATCH_LIMIT + 5)]
    client = _client(_transport({"targets": []}, calls=calls), tmp_path)

    await client.domain_ratings(domains)

    assert len(calls) == 2
    assert len(json.loads(calls[0].content)["targets"]) == BATCH_LIMIT
    assert len(json.loads(calls[1].content)["targets"]) == 5


@pytest.mark.asyncio
async def test_call_cap_raises_before_spending(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    domains = [f"org{n}.org" for n in range(BATCH_LIMIT * 3)]
    client = _client(_transport({"targets": []}, calls=calls), tmp_path, max_calls=1)

    with pytest.raises(AhrefsQuotaExceededError):
        await client.domain_ratings(domains)

    assert len(calls) == 1, "must stop at the cap, not keep spending"


@pytest.mark.asyncio
async def test_empty_input_makes_no_call(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    client = _client(_transport({"targets": []}, calls=calls), tmp_path)

    assert await client.domain_ratings([]) == {}
    assert calls == []


@pytest.mark.asyncio
async def test_missing_dr_is_none_not_zero(tmp_path: Path) -> None:
    """A domain Ahrefs has no data for must not be conflated with a real DR of 0."""
    calls: list[httpx.Request] = []
    payload = {"targets": [{"url": "unknown.org/", "domain_rating": None, "ahrefs_rank": None}]}
    client = _client(_transport(payload, calls=calls), tmp_path)

    ratings = await client.domain_ratings(["unknown.org"])

    assert ratings["unknown.org"].dr is None
