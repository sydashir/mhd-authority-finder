"""Orchestrator: load state → fetch sitemap → parse → diff → save → report.

``run_monitor`` is one site's pipeline. The cross-site driver (CLI / library
caller) is responsible for per-site isolation via :func:`asyncio.gather`
with ``return_exceptions=True`` — if MHD's sitemap is down, AH still runs.
"""

from datetime import UTC, datetime

import structlog

from authority_finder.geo_monitor.models import (
    GeoPage,
    MonitorRun,
    SiteConfig,
    SiteState,
)
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.state import load_state, save_state
from authority_finder.geo_monitor.url_parser import parse_geo_url

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def run_monitor(config: SiteConfig, *, fetcher: SitemapFetcher) -> MonitorRun:
    """Discover newly-added geo pages for one site since the last run."""
    started_at = datetime.now(UTC)
    _log.info("monitor.start", site_id=config.id)

    state = load_state(config.id)

    entries = await fetcher.fetch_all_geo_entries(config)

    parsed: list[GeoPage] = []
    for entry in entries:
        page = parse_geo_url(entry.loc, config, now=started_at)
        if page is not None:
            parsed.append(page)

    current_urls = {page.url for page in parsed}
    new_pages = [page for page in parsed if page.url not in state.known_urls]

    finished_at = datetime.now(UTC)

    save_state(
        config.id,
        SiteState(
            last_run=finished_at,
            known_urls=state.known_urls | current_urls,
        ),
    )

    _log.info(
        "monitor.finish",
        site_id=config.id,
        total_pages=len(parsed),
        new_pages=len(new_pages),
        duration_s=(finished_at - started_at).total_seconds(),
    )

    return MonitorRun(
        site_id=config.id,
        started_at=started_at,
        finished_at=finished_at,
        new_pages=new_pages,
        total_pages=len(parsed),
        errors=[],
    )
