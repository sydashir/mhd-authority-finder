"""Async sitemap fetcher for Rank Math sitemaps.

Two-layer fetch: the sitemap *index* (`/sitemap_index.xml`) lists sub-sitemaps;
each *page sitemap* (`/page-sitemap1.xml`, ...) lists actual page URLs. We
respect ``robots.txt`` (cached once per host), retry transient failures via
tenacity, and cap concurrency per host via an :class:`asyncio.Semaphore`.

Sitemap XML namespace is the standard sitemaps.org schema. ``<lastmod>`` is
parsed via :func:`datetime.fromisoformat`, which in 3.11+ accepts the ``Z``
suffix and date-only strings — best-effort, drops bad values to ``None``.
"""

import asyncio
from datetime import datetime
from http import HTTPStatus
from typing import Protocol
from urllib.parse import urlparse

import httpx
import structlog
from lxml import etree
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from authority_finder.geo_monitor.models import SiteConfig, SitemapEntry
from authority_finder.robots import USER_AGENT, RobotsChecker

DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SitemapSource(Protocol):
    """The sitemap dependency the monitor/scheduler need — a seam for testing."""

    async def fetch_all_geo_entries(self, config: SiteConfig) -> list[SitemapEntry]: ...


class SitemapFetcher:
    """Owns one :class:`httpx.AsyncClient`, one per-host semaphore, one robots checker."""

    def __init__(self, *, client: httpx.AsyncClient, concurrency: int = 2) -> None:
        self._client = client
        self._sem = asyncio.Semaphore(concurrency)
        self._robots = RobotsChecker(client=client, timeout=DEFAULT_TIMEOUT)

    async def fetch_sitemap_index(self, url: str) -> list[str]:
        """Return the list of sub-sitemap URLs from a ``<sitemapindex>`` document."""
        await self._robots.ensure_allowed(url)
        content = await self._get(url)
        root = etree.fromstring(content)
        out: list[str] = []
        for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS):
            if loc.text:
                out.append(loc.text.strip())
        return out

    async def fetch_page_sitemap(self, url: str) -> list[SitemapEntry]:
        """Return all URL entries from a ``<urlset>`` page sitemap."""
        await self._robots.ensure_allowed(url)
        content = await self._get(url)
        root = etree.fromstring(content)
        entries: list[SitemapEntry] = []
        for url_node in root.findall("sm:url", SITEMAP_NS):
            loc = url_node.find("sm:loc", SITEMAP_NS)
            if loc is None or not loc.text:
                continue
            lastmod = url_node.find("sm:lastmod", SITEMAP_NS)
            lastmod_dt: datetime | None = None
            if lastmod is not None and lastmod.text:
                lastmod_dt = _parse_lastmod(lastmod.text.strip())
            entries.append(SitemapEntry(loc=loc.text.strip(), lastmod=lastmod_dt))
        return entries

    async def fetch_all_geo_entries(self, config: SiteConfig) -> list[SitemapEntry]:
        """Fetch all geo entries for a site: index → page sitemaps → regex filter."""
        sub_urls = await self.fetch_sitemap_index(config.sitemap_index_url)
        _log.info("sitemap.index_fetched", site_id=config.id, sub_sitemaps=len(sub_urls))
        page_sitemap_urls: list[str] = []
        for sub_url in sub_urls:
            if "page-sitemap" in sub_url:
                page_sitemap_urls.append(sub_url)
            else:
                _log.info(
                    "sitemap.subsitemap_skipped",
                    site_id=config.id,
                    url=sub_url,
                    reason="no 'page-sitemap' in name; geo pages live in page sitemaps only",
                )
        results = await asyncio.gather(
            *(self.fetch_page_sitemap(u) for u in page_sitemap_urls),
            return_exceptions=True,
        )

        geo_entries: list[SitemapEntry] = []
        for sub_url, result in zip(page_sitemap_urls, results, strict=True):
            if isinstance(result, BaseException):
                _log.warning(
                    "sitemap.subsitemap_failed",
                    site_id=config.id,
                    url=sub_url,
                    error=str(result),
                )
                continue
            for entry in result:
                path = urlparse(entry.loc).path
                # Every known shape, not just the primary: filtering on geo_url_regex alone
                # discarded the topic-prefixed geo pages before the parser could see them,
                # which is how 2,848 MHD pages stayed invisible (ADR-031).
                patterns = (config.geo_url_regex, *config.topic_url_regexes)
                if any(pattern.match(path) for pattern in patterns):
                    geo_entries.append(entry)
        _log.info("sitemap.geo_entries_collected", site_id=config.id, count=len(geo_entries))
        return geo_entries

    async def _get(self, url: str) -> bytes:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=10.0),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
            before_sleep=_log_before_sleep,
        ):
            with attempt:
                async with self._sem:
                    resp = await self._client.get(
                        url,
                        headers={"User-Agent": USER_AGENT, "Accept": "application/xml"},
                        timeout=DEFAULT_TIMEOUT,
                    )
                if resp.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
                    raise httpx.HTTPStatusError(
                        f"{resp.status_code} from {url}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return resp.content
        raise RuntimeError(f"unreachable: AsyncRetrying yielded no attempts for {url}")


def _parse_lastmod(value: str) -> datetime | None:
    """Best-effort ISO 8601 parsing of a sitemap ``<lastmod>`` string.

    Sitemaps allow either full datetime or date-only formats. Python 3.11+
    ``datetime.fromisoformat`` accepts both and the trailing ``Z`` suffix.
    """
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _log_before_sleep(retry_state: RetryCallState) -> None:
    error = retry_state.outcome.exception() if retry_state.outcome is not None else None
    _log.warning(
        "sitemap.retry",
        attempt=retry_state.attempt_number,
        error=str(error) if error else None,
    )


async def fetch_all_geo_entries(config: SiteConfig) -> list[SitemapEntry]:
    """Convenience entry point: build a one-shot fetcher and run it."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        fetcher = SitemapFetcher(client=client)
        return await fetcher.fetch_all_geo_entries(config)
