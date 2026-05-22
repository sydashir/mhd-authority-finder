"""Live integration tests against real MHD + AH sitemaps.

Skipped by default; opt in with ``pytest -m live``. These exist to catch real
sitemap drift: namespace changes, URL pattern surprises, new state slugs we
haven't whitelisted, etc. Costs a few HTTP round-trips and respects
robots.txt — same as the production fetcher.
"""

from datetime import UTC, datetime

import httpx
import pytest

from authority_finder.geo_monitor.models import SiteConfig
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import AH, MHD, SITES
from authority_finder.geo_monitor.states import US_STATE_SLUGS
from authority_finder.geo_monitor.url_parser import parse_geo_url


@pytest.mark.live
@pytest.mark.parametrize("site", [MHD, AH], ids=["mhd", "ah"])
async def test_sitemap_index_returns_subsitemaps(site: SiteConfig) -> None:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        fetcher = SitemapFetcher(client=client)
        sub_urls = await fetcher.fetch_sitemap_index(site.sitemap_index_url)

    assert sub_urls, f"{site.id} sitemap index returned no sub-sitemaps"
    assert any("page-sitemap" in u for u in sub_urls), (
        f"{site.id} sitemap index has no page-sitemap entries"
    )


@pytest.mark.live
@pytest.mark.parametrize("site_id", list(SITES.keys()))
async def test_fetch_all_geo_entries_yields_valid_state_slugs(site_id: str) -> None:
    config = SITES[site_id]
    now = datetime.now(UTC)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        fetcher = SitemapFetcher(client=client)
        entries = await fetcher.fetch_all_geo_entries(config)

    assert entries, f"{site_id} returned zero geo entries"

    parsed_count = 0
    for entry in entries:
        page = parse_geo_url(entry.loc, config, now=now)
        if page is None:
            continue
        parsed_count += 1
        assert page.state in US_STATE_SLUGS, (
            f"{site_id} URL {entry.loc} parsed to unknown state slug {page.state!r}"
        )

    assert parsed_count > 0, f"{site_id} had entries but none parsed to a GeoPage"
