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

from authority_finder.discovery.serpapi_client import QuotaExceededError
from authority_finder.geo_monitor.models import GeoPage, SiteConfig, SiteState
from authority_finder.geo_monitor.monitor import diff_sitemap
from authority_finder.geo_monitor.sitemap_fetcher import SitemapSource
from authority_finder.geo_monitor.state import DEFAULT_STATE_DIR, save_state
from authority_finder.scheduler.models import IncrementalRunResult, RunOutcome

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

RunAndWrite = Callable[[list[GeoPage]], Awaitable[RunOutcome]]
# Effectively "no cap" default; the scheduler passes settings.max_new_geos_per_run (ADR-012).
_UNCAPPED = 10_000


async def run_incremental(
    config: SiteConfig,
    *,
    sitemap_fetcher: SitemapSource,
    run_and_write: RunAndWrite,
    now: datetime,
    max_new_geos: int = _UNCAPPED,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> IncrementalRunResult:
    """Run the pipeline for newly-discovered geos only; persist state on success.

    Caps the batch at ``max_new_geos`` (a site re-publishing its whole sitemap must
    not blow through quota); the overflow is deferred to the next tick. State is
    persisted only after a successful run and only for the geos actually processed,
    so deferred/failed geos retry next tick.
    """
    diff = await diff_sitemap(config, fetcher=sitemap_fetcher, now=now, state_dir=state_dir)
    new_pages = diff.new_pages

    if not new_pages:
        _log.info("incremental.no_new_geos", site_id=config.id, total=diff.total_parsed)
        return IncrementalRunResult(site_id=config.id)

    to_process = new_pages[:max_new_geos]
    deferred = new_pages[max_new_geos:]
    if deferred:
        _log.warning(
            "incremental.capped",
            site_id=config.id,
            new_geos=len(new_pages),
            cap=max_new_geos,
            processing=len(to_process),
            deferred=len(deferred),
        )
    _log.info("incremental.new_geos", site_id=config.id, count=len(to_process))

    try:
        outcome = await run_and_write(to_process)
    except QuotaExceededError as exc:
        _log.error("incremental.circuit_breaker", site_id=config.id, error=str(exc))
        return IncrementalRunResult(
            site_id=config.id,
            new_geos_found=len(new_pages),
            deferred=len(deferred),
            aborted=True,
            note=f"circuit breaker: {exc}",
        )
    except Exception as exc:
        # Crash mid-run: do NOT persist state — these geos retry next tick.
        _log.error("incremental.aborted", site_id=config.id, error=str(exc))
        return IncrementalRunResult(
            site_id=config.id,
            new_geos_found=len(new_pages),
            deferred=len(deferred),
            note=str(exc),
            aborted=True,
        )

    save_state(
        config.id,
        SiteState(last_run=now, known_urls=diff.prior_known_urls | {p.url for p in to_process}),
        state_dir=state_dir,
    )
    _log.info(
        "incremental.finished",
        site_id=config.id,
        processed=len(to_process),
        deferred=len(deferred),
        rows_written=outcome.rows_written,
        billed_searches=outcome.billed_searches,
    )
    return IncrementalRunResult(
        site_id=config.id,
        new_geos_found=len(new_pages),
        processed=len(to_process),
        deferred=len(deferred),
        rows_written=outcome.rows_written,
        billed_searches=outcome.billed_searches,
    )
