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


class TestWidenedDepth:
    """Depth is pure volume on the source that already works (S30).

    Every added theme must be a DISTINCT angle — duplicating a theme spends a billed
    search to re-fetch the same page-1 results.
    """

    def _geo(self, level: str) -> GeoPage:
        return GeoPage(
            site_id="mhd",
            url="https://inpatientmentalhealthfinder.com/serving/texas/travis/austin/",
            level=level,  # pyright: ignore[reportArgumentType]
            state="texas",
            county="travis",
            city="austin",
            first_seen=datetime(2026, 7, 30, tzinfo=UTC),
        )

    def test_each_level_has_at_least_eight_queries(self) -> None:
        for level in ("state", "county", "city"):
            assert len(build_queries(self._geo(level))) >= 8, level

    def test_queries_are_unique_within_a_level(self) -> None:
        for level in ("state", "county", "city"):
            queries = build_queries(self._geo(level))
            assert len(queries) == len(set(queries)), level

    def test_every_query_keeps_the_gov_edu_restriction(self) -> None:
        """Discovery stays scoped; the unrestricted source is authority_filter's job."""
        for level in ("state", "county", "city"):
            for query in build_queries(self._geo(level)):
                assert "site:" in query, f"{level}: {query}"

    def test_themes_do_not_merely_repeat_one_keyword(self) -> None:
        """Guards against padding the list with near-duplicates of 'mental health'."""
        queries = build_queries(self._geo("state"))
        mental = sum(1 for q in queries if "mental health" in q.lower())
        assert mental <= len(queries) // 2
