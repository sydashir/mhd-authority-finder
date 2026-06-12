"""Unit tests for the pure query builder."""

from datetime import UTC, datetime

import pytest

from authority_finder.discovery.queries import (
    CITY_QUERIES,
    COUNTY_QUERIES,
    STATE_QUERIES,
    build_queries,
    county_display,
    slug_to_display,
)
from authority_finder.geo_monitor.models import GeoLevel, GeoPage


def _geo(
    level: GeoLevel, state: str, county: str | None = None, city: str | None = None
) -> GeoPage:
    return GeoPage(
        url=f"https://example.com/serving/{state}/",
        site_id="mhd",
        state=state,
        county=county,
        city=city,
        level=level,
        first_seen=datetime.now(UTC),
    )


def test_slug_to_display_simple() -> None:
    assert slug_to_display("maryland") == "Maryland"


def test_slug_to_display_multi_word() -> None:
    assert slug_to_display("north-carolina") == "North Carolina"


def test_slug_to_display_best_effort_edge() -> None:
    assert slug_to_display("st-louis") == "St Louis"


def test_county_display_strips_redundant_suffix() -> None:
    assert county_display("orange-county") == "Orange"


def test_county_display_keeps_plain_names() -> None:
    assert county_display("los-angeles") == "Los Angeles"


def test_state_queries() -> None:
    queries = build_queries(_geo("state", "maryland"))
    assert len(queries) == len(STATE_QUERIES)
    assert queries[0] == "Maryland mental health resources (site:.gov OR site:.edu)"
    assert all("Maryland" in q for q in queries)


def test_county_queries_normalize_county_suffix() -> None:
    queries = build_queries(_geo("county", "california", county="orange-county"))
    assert len(queries) == len(COUNTY_QUERIES)
    assert queries[0] == '"Orange County" California health department site:.gov'
    assert all("County County" not in q for q in queries)


def test_city_queries() -> None:
    geo = _geo("city", "california", county="orange-county", city="newport-beach")
    queries = build_queries(geo)
    assert len(queries) == len(CITY_QUERIES)
    assert queries[0] == '"Newport Beach" California health department site:.gov'
    assert all("Newport Beach" in q for q in queries)


def test_county_level_without_county_slug_raises() -> None:
    with pytest.raises(ValueError, match="county-level geo"):
        build_queries(_geo("county", "california"))


def test_city_level_without_city_slug_raises() -> None:
    with pytest.raises(ValueError, match="city-level geo"):
        build_queries(_geo("city", "california", county="orange-county"))
