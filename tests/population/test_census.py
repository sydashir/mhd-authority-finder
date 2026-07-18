"""Census population lookup: FIPS, fuzzy match, disambiguation, sentinels, cache.

No network and no key — a MockTransport returns ACS-shaped array-of-arrays
keyed on the (for, in) params, and fixtures are injected directly.
"""

from datetime import UTC, datetime
from pathlib import Path

import httpx

from authority_finder.geo_monitor.models import GeoLevel, GeoPage
from authority_finder.population.census import CensusClient, normalize_place

POP = "B01003_001E"

# (for, in) -> array-of-arrays response (header + rows)
RESPONSES: dict[tuple[str, str | None], list[list[str]]] = {
    ("state:24", None): [["NAME", POP, "state"], ["Maryland", "6164660", "24"]],
    ("state:06", None): [["NAME", POP, "state"], ["California", "39538223", "06"]],
    ("county:*", "state:06"): [
        ["NAME", POP, "state", "county"],
        ["Orange County, California", "3170345", "06", "059"],
        ["Los Angeles County, California", "9829544", "06", "037"],
    ],
    ("place:*", "state:06"): [
        ["NAME", POP, "state", "place"],
        ["Newport Beach city, California", "85239", "06", "51182"],
        ["Los Angeles city, California", "3820914", "06", "44000"],
        # A real-but-unrelated decoy: "Palos Verdes" (a peninsula/neighborhood, not a
        # Census place) string-matches this tiny Imperial-County CDP at ratio ~0.91.
        ["Palo Verde CDP, California", "75", "06", "55044"],
    ],
    ("place:*", "state:29"): [
        ["NAME", POP, "state", "place"],
        ["St. Louis city, Missouri", "281754", "29", "65000"],
    ],
    ("place:*", "state:17"): [
        ["NAME", POP, "state", "place"],
        ["Springfield city, Illinois", "114394", "17", "72000"],
    ],
    # A suppressed value (ACS jam sentinel).
    ("county:*", "state:24"): [
        ["NAME", POP, "state", "county"],
        ["Kent County, Maryland", "-666666666", "24", "029"],
    ],
}


def _handler(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    key = (params.get("for"), params.get("in"))
    if key in RESPONSES:
        return httpx.Response(200, json=RESPONSES[key])
    return httpx.Response(200, json=[["NAME", POP]])  # empty result set


def _client(
    tmp_path: Path, *, api_key: str = "test-key", counter: list[str] | None = None
) -> CensusClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if counter is not None:
            counter.append(str(request.url))
        return _handler(request)

    transport = httpx.MockTransport(handler)
    return CensusClient(
        client=httpx.AsyncClient(transport=transport), api_key=api_key, cache_dir=tmp_path
    )


def _geo(
    level: GeoLevel, state: str, county: str | None = None, city: str | None = None
) -> GeoPage:
    return GeoPage(
        url="https://x/y",
        site_id="mhd",
        state=state,
        county=county,
        city=city,
        level=level,
        first_seen=datetime.now(UTC),
    )


def test_normalize_strips_suffix_and_state() -> None:
    assert normalize_place("Orange County, California") == "orange"
    assert normalize_place("Newport Beach city, California") == "newport beach"
    assert normalize_place("St. Louis city, Missouri") == "saint louis"
    assert normalize_place("Doña Ana County, New Mexico") == "dona ana"


async def test_state_population_exact(tmp_path: Path) -> None:
    result = await _client(tmp_path).population_for(_geo("state", "maryland"))
    assert result.value == 6164660
    assert result.confidence == "exact"
    assert result.geo_level_used == "state"
    assert result.matched_name == "Maryland"


async def test_county_exact_match(tmp_path: Path) -> None:
    result = await _client(tmp_path).population_for(
        _geo("county", "california", county="orange-county")
    )
    assert result.value == 3170345
    assert result.confidence == "exact"
    assert result.matched_name == "Orange County, California"


async def test_city_exact_match(tmp_path: Path) -> None:
    result = await _client(tmp_path).population_for(
        _geo("city", "california", county="orange-county", city="newport-beach")
    )
    assert result.value == 85239
    assert result.geo_level_used == "place"
    assert result.confidence == "exact"


async def test_city_scoped_to_state_disambiguates(tmp_path: Path) -> None:
    # "springfield" exists in many states; the place:* query is scoped to IL (17),
    # so only the Illinois Springfield is a candidate.
    result = await _client(tmp_path).population_for(_geo("city", "illinois", city="springfield"))
    assert result.matched_name == "Springfield city, Illinois"
    assert result.value == 114394


async def test_punctuation_fuzzy_match(tmp_path: Path) -> None:
    # slug "st-louis" -> "St Louis" -> normalized "saint louis" == census "St. Louis city".
    result = await _client(tmp_path).population_for(_geo("city", "missouri", city="st-louis"))
    assert result.matched_name == "St. Louis city, Missouri"
    assert result.value == 281754


async def test_neighborhood_not_found(tmp_path: Path) -> None:
    result = await _client(tmp_path).population_for(
        _geo("city", "california", county="los-angeles", city="downtown-los-angeles")
    )
    assert result.confidence == "not_found"
    assert result.value is None


async def test_ambiguous_neighborhood_not_fuzzy_matched_to_wrong_place(tmp_path: Path) -> None:
    # "palos-verdes" (a peninsula, not a Census place) is ~0.91 string-similar to the unrelated
    # "Palo Verde CDP" (pop 75). It must NOT match — not_found is the honest result (Session 12).
    result = await _client(tmp_path).population_for(
        _geo("city", "california", county="los-angeles", city="palos-verdes")
    )
    assert result.confidence == "not_found"
    assert result.value is None


async def test_suppressed_value_is_none_but_matched(tmp_path: Path) -> None:
    result = await _client(tmp_path).population_for(
        _geo("county", "maryland", county="kent-county")
    )
    assert result.matched_name == "Kent County, Maryland"
    assert result.value is None  # -666666666 sentinel rejected


async def test_no_key_degrades_to_not_found(tmp_path: Path) -> None:
    result = await _client(tmp_path, api_key="").population_for(_geo("state", "maryland"))
    assert result.confidence == "not_found"
    assert "CENSUS_API_KEY" in result.note


async def test_invalid_key_fails_loudly_with_clear_note(tmp_path: Path) -> None:
    # An expired/invalid CENSUS_API_KEY makes the API return a 200 HTML "Invalid Key" page
    # (not JSON). It must surface a CLEAR not_found note, not silently degrade — the exact
    # failure that hid the S24 population gap (ADR-024, bucket E).
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><head><title>Invalid Key</title></head></html>",
            headers={"content-type": "text/html"},
        )

    client = CensusClient(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        api_key="bad-key",
        cache_dir=tmp_path,
    )
    result = await client.population_for(_geo("state", "alabama"))
    assert result.confidence == "not_found"
    assert "invalid" in result.note.lower() and "key" in result.note.lower()


async def test_cache_avoids_second_request(tmp_path: Path) -> None:
    counter: list[str] = []
    client = _client(tmp_path, counter=counter)
    geo = _geo("city", "california", county="orange-county", city="newport-beach")
    await client.population_for(geo)
    first = len(counter)
    await client.population_for(geo)
    assert len(counter) == first  # second call served from disk cache
