"""Orchestrator: load state → fetch sitemap → parse → diff → save → report.

``run_monitor`` is one site's pipeline. The cross-site driver (CLI / library
caller) is responsible for per-site isolation via :func:`asyncio.gather`
with ``return_exceptions=True`` — if MHD's sitemap is down, AH still runs.

:func:`diff_sitemap` is the pure detect-only half (fetch + parse + diff, **no
persistence**). The scheduler's incremental runner uses it so state is saved
only after a successful pipeline run — never marking a geo "seen" before it's
been processed (ADR-012). ``run_monitor`` keeps its original behaviour: detect
then immediately persist the full current set.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import structlog

from authority_finder.geo_monitor.models import (
    GeoPage,
    MonitorRun,
    SiteConfig,
    SiteState,
)
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher, SitemapSource
from authority_finder.geo_monitor.state import DEFAULT_STATE_DIR, load_state, save_state
from authority_finder.geo_monitor.url_parser import parse_geo_url

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SitemapDiff(NamedTuple):
    """Detect-only result: new pages plus the context needed to persist later."""

    new_pages: list[GeoPage]
    current_urls: set[str]
    prior_known_urls: set[str]
    started_at: datetime
    total_parsed: int


async def diff_sitemap(
    config: SiteConfig,
    *,
    fetcher: SitemapSource,
    now: datetime | None = None,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> SitemapDiff:
    """Fetch + parse + diff a site's sitemap against saved state. Does NOT persist."""
    started_at = now or datetime.now(UTC)
    state = load_state(config.id, state_dir=state_dir)
    entries = await fetcher.fetch_all_geo_entries(config)

    parsed: list[GeoPage] = []
    for entry in entries:
        page = parse_geo_url(entry.loc, config, now=started_at)
        if page is not None:
            parsed.append(page)

    current_urls = {page.url for page in parsed}
    new_pages = [page for page in parsed if page.url not in state.known_urls]
    return SitemapDiff(
        new_pages=new_pages,
        current_urls=current_urls,
        prior_known_urls=state.known_urls,
        started_at=started_at,
        total_parsed=len(parsed),
    )


async def run_monitor(config: SiteConfig, *, fetcher: SitemapFetcher) -> MonitorRun:
    """Discover newly-added geo pages for one site since the last run, then persist."""
    _log.info("monitor.start", site_id=config.id)
    diff = await diff_sitemap(config, fetcher=fetcher)
    finished_at = datetime.now(UTC)

    save_state(
        config.id,
        SiteState(last_run=finished_at, known_urls=diff.prior_known_urls | diff.current_urls),
    )

    _log.info(
        "monitor.finish",
        site_id=config.id,
        total_pages=diff.total_parsed,
        new_pages=len(diff.new_pages),
        duration_s=(finished_at - diff.started_at).total_seconds(),
    )

    return MonitorRun(
        site_id=config.id,
        started_at=diff.started_at,
        finished_at=finished_at,
        new_pages=diff.new_pages,
        total_pages=diff.total_parsed,
        errors=[],
    )
