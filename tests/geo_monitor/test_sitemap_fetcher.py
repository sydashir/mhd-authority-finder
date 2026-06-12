"""Unit tests for ``SitemapFetcher`` against a mocked transport — no network."""

import httpx
import structlog

from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import MHD

INDEX_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://inpatientmentalhealthfinder.com/page-sitemap.xml</loc></sitemap>
  <sitemap><loc>https://inpatientmentalhealthfinder.com/facilites-sitemap.xml</loc></sitemap>
  <sitemap><loc>https://inpatientmentalhealthfinder.com/local-sitemap.xml</loc></sitemap>
</sitemapindex>
"""

PAGE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://inpatientmentalhealthfinder.com/serving/california/</loc></url>
  <url><loc>https://inpatientmentalhealthfinder.com/about/</loc></url>
</urlset>
"""


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(404)
    if path == "/sitemap_index.xml":
        return httpx.Response(200, content=INDEX_XML)
    if path == "/page-sitemap.xml":
        return httpx.Response(200, content=PAGE_XML)
    raise AssertionError(f"unexpected fetch: {request.url}")


async def test_skips_non_page_sitemaps_and_logs_each() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        fetcher = SitemapFetcher(client=client)
        with structlog.testing.capture_logs() as logs:
            entries = await fetcher.fetch_all_geo_entries(MHD)

    assert [e.loc for e in entries] == [
        "https://inpatientmentalhealthfinder.com/serving/california/"
    ]
    skipped = [log for log in logs if log["event"] == "sitemap.subsitemap_skipped"]
    assert {log["url"] for log in skipped} == {
        "https://inpatientmentalhealthfinder.com/facilites-sitemap.xml",
        "https://inpatientmentalhealthfinder.com/local-sitemap.xml",
    }
    assert all(log["site_id"] == "mhd" for log in skipped)
    assert all(log["reason"] for log in skipped)
