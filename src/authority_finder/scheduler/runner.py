"""Scheduler entrypoint: in-process APScheduler driving incremental runs (ADR-012).

In-process APScheduler (3.x ``AsyncIOScheduler``) over system cron so the same
command runs identically on the user's Mac and in a container — no host-level
cron to configure. Each tick runs the incremental "new geos only" pipeline for
both sites with per-site isolation (MHD failing never stops AH); the costly
clients (Playwright browser, SerpAPI) are built lazily inside ``run_and_write``,
so a tick with no new geos opens no browser and spends nothing.
"""

import asyncio
import signal
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import sentry_sdk
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from authority_finder.config import Settings, get_settings
from authority_finder.db.ingest import persist_pipeline_run
from authority_finder.db.repository import run_rejection_reason
from authority_finder.db.session import make_engine, make_session_factory
from authority_finder.discovery.serpapi_client import SerpApiClient
from authority_finder.fetching import PageFetcher
from authority_finder.fetching.browser import PlaywrightBrowserFetcher
from authority_finder.geo_monitor.models import GeoPage, SiteConfig
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher, SitemapSource
from authority_finder.geo_monitor.sites import SITES
from authority_finder.geo_monitor.state import DEFAULT_STATE_DIR
from authority_finder.output.sheets_writer import SheetsWriter
from authority_finder.pipeline import run_pipeline
from authority_finder.population.census import CensusClient
from authority_finder.scheduler.incremental import RunAndWrite, run_incremental
from authority_finder.scheduler.models import IncrementalRunResult, RunOutcome
from authority_finder.scheduler.schedule import ScheduleSpec

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

BuildRunAndWrite = Callable[[SiteConfig], RunAndWrite]


async def run_tick(
    *,
    sitemap_fetcher: SitemapSource,
    build_run_and_write: BuildRunAndWrite,
    now: datetime,
    max_new_geos: int = 1000,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> list[IncrementalRunResult]:
    """Run the incremental pipeline for every site, isolating per-site failures."""
    results: list[IncrementalRunResult] = []
    for site_id, config in SITES.items():
        try:
            result = await run_incremental(
                config,
                sitemap_fetcher=sitemap_fetcher,
                run_and_write=build_run_and_write(config),
                now=now,
                max_new_geos=max_new_geos,
                state_dir=state_dir,
            )
        except Exception as exc:
            _log.error("scheduler.site_failed", site_id=site_id, error=str(exc))
            # A scheduled run failing (the 3am cron) must alert someone (no-op if no DSN).
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("site_id", site_id)
                sentry_sdk.capture_exception(exc)
            result = IncrementalRunResult(site_id=site_id, aborted=True, note=str(exc))
        results.append(result)
    return results


def _make_run_and_write(
    *,
    settings: Settings,
    now: datetime,
    sessionmaker: async_sessionmaker[AsyncSession],
    site: str,
) -> RunAndWrite:
    """Build the pipeline+persist+export closure; costly clients are created only when called.

    Postgres is the source of truth (ADR-025): persist prospects + record the run FIRST, then
    export to the Google Sheet. The upsert preserves the team's outreach fields (ADR-022), so a
    scheduled re-run of a known geo never clobbers a note.
    """

    async def _run_and_write(geos: list[GeoPage]) -> RunOutcome:
        browser = PlaywrightBrowserFetcher(no_sandbox=settings.playwright_no_sandbox)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                serp = SerpApiClient(
                    client=client,
                    api_key=settings.serpapi_api_key,
                    max_billed=settings.max_billed_searches_per_run,
                )
                rows, funnel = await run_pipeline(
                    geos,
                    serp_client=serp,
                    fetcher=PageFetcher(client=client, browser=browser),
                    census_client=CensusClient(
                        client=client, api_key=settings.census_api_key.get_secret_value()
                    ),
                    now=now,
                )
            finally:
                await browser.aclose()

        async with sessionmaker() as session:
            await persist_pipeline_run(
                session, rows=rows, geos=geos, site=site, billed_searches=funnel.billed_searches
            )
            await session.commit()

        writer = SheetsWriter(
            credentials_path=settings.google_sheets_credentials_path,
            spreadsheet_id=settings.google_sheet_id,
        )
        result = await writer.write(rows)  # append-only, idempotent on (Website, Geo)
        return RunOutcome(rows_written=result.appended, billed_searches=funnel.billed_searches)

    return _run_and_write


async def scheduled_tick(
    *, settings: Settings | None = None, state_dir: Path = DEFAULT_STATE_DIR
) -> list[IncrementalRunResult]:
    """One real tick: monitor + incremental pipeline for both sites, fully wired."""
    settings = settings or get_settings()
    now = datetime.now(UTC)
    _log.info("scheduler.tick_start", at=now.isoformat())
    engine = make_engine(settings.database_url)
    sessionmaker = make_session_factory(engine)
    try:
        # Respect the shared cost rails (ADR-025): if a run is already in progress (e.g. an API
        # trigger) or the daily budget is spent, skip this tick rather than collide/overspend.
        async with sessionmaker() as session:
            reason = await run_rejection_reason(
                session, max_billed_per_day=settings.max_billed_searches_per_day
            )
        if reason is not None:
            _log.warning("scheduler.tick_skipped", reason=reason)
            return []
        async with httpx.AsyncClient(follow_redirects=True) as sitemap_client:
            fetcher = SitemapFetcher(client=sitemap_client)
            results = await run_tick(
                sitemap_fetcher=fetcher,
                build_run_and_write=lambda cfg: _make_run_and_write(
                    settings=settings, now=now, sessionmaker=sessionmaker, site=cfg.id
                ),
                now=now,
                max_new_geos=settings.max_new_geos_per_run,
                state_dir=state_dir,
            )
    finally:
        await engine.dispose()
    _log.info(
        "scheduler.tick_finish",
        new_geos=sum(r.new_geos_found for r in results),
        rows_written=sum(r.rows_written for r in results),
        billed_searches=sum(r.billed_searches for r in results),
        aborted=[r.site_id for r in results if r.aborted],
    )
    return results


async def run_scheduler(
    *, spec: ScheduleSpec, run_now: bool = True, state_dir: Path = DEFAULT_STATE_DIR
) -> None:
    """Start the in-process scheduler on a day-of-week cron and run until SIGINT/SIGTERM.

    Named days at a fixed LOCAL time, not an interval: an interval drifts with every restart,
    and it is not what "Mondays and Wednesdays at 3am" means. The timezone is the client's,
    not the server's — see :mod:`authority_finder.scheduler.schedule`.
    """
    settings = get_settings()
    # APScheduler ships no type stubs; contain its dynamic surface behind Any.
    scheduler: Any = AsyncIOScheduler()
    scheduler.add_job(
        lambda: scheduled_tick(settings=settings, state_dir=state_dir),
        CronTrigger(**spec.as_cron_kwargs()),
        id="incremental",
        next_run_time=datetime.now() if run_now else None,  # local tz (APScheduler), run-once now
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        replace_existing=True,
    )
    scheduler.start()
    _log.info("scheduler.started", schedule=spec.describe(), run_now=run_now)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        _log.info("scheduler.stopping")
        scheduler.shutdown(wait=True)
