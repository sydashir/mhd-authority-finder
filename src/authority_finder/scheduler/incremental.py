"""Incremental "new geos only" pipeline run — the cost-safety core (ADR-012).

Detects newly-published geo pages (sitemap diff, no persistence), runs the full
chain for ONLY those, appends to the sheet, and persists monitor state **only
after** a successful run — and only for the geos actually processed, so a crash
or circuit-breaker abort retries them next tick instead of silently skipping.

The pipeline itself is injected as ``run_and_write`` (a callable over the new
geos returning a :class:`RunOutcome`) so this orchestration — the part that must
never spend SerpAPI on already-seen geos — is unit-testable without any network.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

import structlog

from authority_finder.geo_monitor.models import GeoPage, SiteConfig, SiteState
from authority_finder.geo_monitor.monitor import diff_sitemap
from authority_finder.geo_monitor.sitemap_fetcher import SitemapSource
from authority_finder.geo_monitor.state import DEFAULT_STATE_DIR, save_state
from authority_finder.scheduler.models import IncrementalRunResult, RunOutcome

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

RunAndWrite = Callable[[list[GeoPage]], Awaitable[RunOutcome]]


async def run_incremental(
    config: SiteConfig,
    *,
    sitemap_fetcher: SitemapSource,
    run_and_write: RunAndWrite,
    now: datetime,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> IncrementalRunResult:
    """Run the pipeline for newly-discovered geos only; persist state on success."""
    diff = await diff_sitemap(config, fetcher=sitemap_fetcher, now=now, state_dir=state_dir)
    new_pages = diff.new_pages

    if not new_pages:
        _log.info("incremental.no_new_geos", site_id=config.id, total=diff.total_parsed)
        return IncrementalRunResult(site_id=config.id)

    _log.info("incremental.new_geos", site_id=config.id, count=len(new_pages))
    try:
        outcome = await run_and_write(new_pages)
    except Exception as exc:
        # Crash mid-run: do NOT persist state — these geos retry next tick.
        _log.error("incremental.aborted", site_id=config.id, error=str(exc))
        return IncrementalRunResult(
            site_id=config.id, new_geos_found=len(new_pages), aborted=True, note=str(exc)
        )

    save_state(
        config.id,
        SiteState(last_run=now, known_urls=diff.prior_known_urls | {p.url for p in new_pages}),
        state_dir=state_dir,
    )
    _log.info(
        "incremental.finished",
        site_id=config.id,
        processed=len(new_pages),
        rows_written=outcome.rows_written,
        billed_searches=outcome.billed_searches,
    )
    return IncrementalRunResult(
        site_id=config.id,
        new_geos_found=len(new_pages),
        processed=len(new_pages),
        rows_written=outcome.rows_written,
        billed_searches=outcome.billed_searches,
    )
