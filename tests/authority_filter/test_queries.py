"""Unrestricted authority queries. Pure — no I/O, no billed searches."""

from datetime import UTC, datetime

from authority_finder.authority_filter.queries import build_authority_queries
from authority_finder.geo_monitor.models import GeoPage


def _geo(level: str, **kw: str) -> GeoPage:
    return GeoPage(
        site_id="ah",
        url=f"https://addictionhotline.com/{kw.get('state', 'alabama')}/",
        level=level,  # pyright: ignore[reportArgumentType]  - literal narrowed by GeoPage
        state=kw.get("state", "alabama"),
        county=kw.get("county"),
        city=kw.get("city"),
        first_seen=datetime(2026, 7, 30, tzinfo=UTC),
    )


class TestNoSiteFilter:
    def test_no_query_carries_a_site_filter(self) -> None:
        """The whole point of component 3: ``site:.gov OR site:.edu`` structurally cannot
        return ncala.org, which is why ADR-006's ``other`` bucket sat at zero."""
        for level in ("state", "county", "city"):
            geo = _geo(level, county="jefferson", city="birmingham")
            queries = build_authority_queries(geo)
            assert queries, f"no queries for {level}"
            for query in queries:
                assert "site:" not in query.lower(), f"{level}: {query}"


class TestGeoIsPresent:
    def test_state_queries_name_the_state(self) -> None:
        queries = build_authority_queries(_geo("state", state="alabama"))
        assert all("Alabama" in q for q in queries)

    def test_county_queries_name_the_county_and_state(self) -> None:
        geo = _geo("county", state="alabama", county="jefferson")
        queries = build_authority_queries(geo)
        assert queries
        assert all("Jefferson" in q and "Alabama" in q for q in queries)

    def test_city_queries_name_the_city_and_state(self) -> None:
        geo = _geo("city", state="alabama", county="jefferson", city="birmingham")
        queries = build_authority_queries(geo)
        assert queries
        assert all("Birmingham" in q and "Alabama" in q for q in queries)

    def test_county_display_does_not_double_the_word_county(self) -> None:
        geo = _geo("county", state="california", county="orange-county")
        assert not any("County County" in q for q in build_authority_queries(geo))


class TestThemes:
    def test_targets_the_org_types_the_brief_names(self) -> None:
        """Coalitions, associations, councils — the ncala.org class, not health departments."""
        joined = " ".join(build_authority_queries(_geo("state"))).lower()
        for theme in ("coalition", "association", "council"):
            assert theme in joined

    def test_queries_are_unique(self) -> None:
        queries = build_authority_queries(_geo("state"))
        assert len(queries) == len(set(queries))
