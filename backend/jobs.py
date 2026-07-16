"""Background pipeline execution for POST /runs (ADR-014).

The endpoint returns a run_id immediately; the work happens here, in a FastAPI
BackgroundTask. The request's session is closed by the time this runs, so every
function opens its OWN session from the injected ``sessionmaker`` (never reuses a
request session or an ORM object).

The actual pipeline reuses the S11 cost-safe machinery: ``incremental`` mode runs
``run_incremental`` per site (process only newly-published geos; a no-new-geos run
spends nothing) and ``full`` mode re-runs every known geo. Both write to BOTH the
Google Sheet (permanent output) and Postgres (under the run_id), and both respect
the S11 cost rails — ``max_new_geos_per_run`` and the ``max_billed`` circuit breaker.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
import sentry_sdk
import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from authority_finder.config import Settings
from authority_finder.db.ingest import persist_prospects
from authority_finder.db.models import Run, RunStatus
from authority_finder.db.repository import finish_run
from authority_finder.discovery.serpapi_client import QuotaExceededError, SerpApiClient
from authority_finder.fetching import PageFetcher
from authority_finder.fetching.browser import PlaywrightBrowserFetcher
from authority_finder.geo_monitor.models import GeoPage, SiteConfig
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import SITES
from authority_finder.geo_monitor.state import DEFAULT_STATE_DIR, load_state
from authority_finder.geo_monitor.url_parser import parse_geo_url
from authority_finder.output.sheets_writer import SheetsWriter
from authority_finder.pipeline import run_pipeline
from authority_finder.population.census import CensusClient
from authority_finder.scheduler.incremental import run_incremental
from authority_finder.scheduler.models import IncrementalRunResult, RunOutcome

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RunSummary:
    """What one triggered run produced — drives how the run row is finalized."""

    geos_processed: int
    rows_written: int
    billed_searches: int
    aborted: bool
    note: str | None


# (run_id, site, mode) -> summary. Injected so tests can mock the pipeline away.
RunJob = Callable[[int, str, str], Awaitable[RunSummary]]


async def execute_run(
    sessionmaker: async_sessionmaker[AsyncSession],
    run_id: int,
    job: RunJob,
    *,
    site: str,
    mode: str,
) -> None:
    """Run ``job`` and finalize the run row — success, or failed (never stuck running).

    Failure is finalized in a SEPARATE fresh session: if the job raised mid-write its
    own session may be poisoned, so we never reuse it to record the failure.
    """
    try:
        summary = await job(run_id, site, mode)
    except Exception as exc:
        _log.error("api.run.failed", run_id=run_id, site=site, error=str(exc))
        # A background run failing (e.g. a scheduled 3am run) is exactly what must alert
        # someone — no request context wraps it, so capture it explicitly (no-op if no DSN).
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("run_id", run_id)
            scope.set_tag("site", site)
            scope.set_tag("mode", mode)
            sentry_sdk.capture_exception(exc)
        async with sessionmaker() as session:
            await finish_run(
                session,
                run_id,
                geos_processed=0,
                rows_written=0,
                billed_searches=0,
                status=RunStatus.failed,
                error_summary=str(exc)[:1000],
            )
            await session.commit()
        return

    status = RunStatus.failed if summary.aborted else RunStatus.success
    async with sessionmaker() as session:
        await finish_run(
            session,
            run_id,
            geos_processed=summary.geos_processed,
            rows_written=summary.rows_written,
            billed_searches=summary.billed_searches,
            status=status,
            error_summary=summary.note,
        )
        await session.commit()
    _log.info("api.run.finished", run_id=run_id, status=status.value, **_summary_log(summary))


def _summary_log(s: RunSummary) -> dict[str, int]:
    return {"geos": s.geos_processed, "rows": s.rows_written, "billed": s.billed_searches}


async def sweep_orphan_runs(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Flip any rows stuck ``running`` (a prior process died mid-run) to ``failed``.

    Run at startup so the run history never shows a perpetually-running ghost.
    Returns the number swept.
    """
    async with sessionmaker() as session:
        result = await session.execute(
            update(Run)
            .where(Run.status == RunStatus.running)
            .values(status=RunStatus.failed, error_summary="orphaned by process restart")
            .returning(Run.id)
        )
        swept = len(result.scalars().all())
        await session.commit()
    if swept:
        _log.warning("api.run.orphans_swept", count=swept)
    return swept


def _site_configs(site: str) -> list[SiteConfig]:
    if site == "both":
        return list(SITES.values())
    config = SITES.get(site)
    if config is None:
        raise ValueError(f"unknown site: {site}")
    return [config]


def _make_run_and_write(
    *,
    run_id: int,
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    now: datetime,
) -> Callable[[list[GeoPage]], Awaitable[RunOutcome]]:
    """Pipeline closure that writes BOTH the Sheet (permanent) AND Postgres (run_id).

    The costly clients are built only when there are geos to process, so a no-new-geos
    run opens no browser and spends nothing. SerpAPI is capped by the circuit breaker.
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

        writer = SheetsWriter(
            credentials_path=settings.google_sheets_credentials_path,
            spreadsheet_id=settings.google_sheet_id,
        )
        sheet_result = await writer.write(rows)  # permanent output, append-only idempotent
        async with sessionmaker() as session:
            await persist_prospects(session, rows=rows, geos=geos, run_id=run_id)
            await session.commit()
        return RunOutcome(
            rows_written=sheet_result.appended, billed_searches=funnel.billed_searches
        )

    return _run_and_write


def _aggregate(results: list[IncrementalRunResult]) -> RunSummary:
    note = "; ".join(r.note for r in results if r.note) or None
    return RunSummary(
        geos_processed=sum(r.processed for r in results),
        rows_written=sum(r.rows_written for r in results),
        billed_searches=sum(r.billed_searches for r in results),
        aborted=any(r.aborted for r in results),
        note=note,
    )


async def _run_incremental(
    run_id: int,
    site: str,
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    now: datetime,
    state_dir: Path,
) -> RunSummary:
    results: list[IncrementalRunResult] = []
    async with httpx.AsyncClient(follow_redirects=True) as sitemap_client:
        fetcher = SitemapFetcher(client=sitemap_client)
        for config in _site_configs(site):
            results.append(
                await run_incremental(
                    config,
                    sitemap_fetcher=fetcher,
                    run_and_write=_make_run_and_write(
                        run_id=run_id, sessionmaker=sessionmaker, settings=settings, now=now
                    ),
                    now=now,
                    max_new_geos=settings.max_new_geos_per_run,
                    state_dir=state_dir,
                )
            )
    return _aggregate(results)


def _known_geos(site: str, *, now: datetime, state_dir: Path) -> list[GeoPage]:
    geos: list[GeoPage] = []
    for config in _site_configs(site):
        state = load_state(config.id, state_dir=state_dir)
        for url in sorted(state.known_urls):
            geo = parse_geo_url(url, config, now=now)
            if geo is not None:
                geos.append(geo)
    return geos


async def _run_full(
    run_id: int,
    site: str,
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    now: datetime,
    state_dir: Path,
) -> RunSummary:
    geos = _known_geos(site, now=now, state_dir=state_dir)
    if not geos:
        return RunSummary(0, 0, 0, aborted=False, note="no known geos")
    run_and_write = _make_run_and_write(
        run_id=run_id, sessionmaker=sessionmaker, settings=settings, now=now
    )
    try:
        outcome = await run_and_write(geos)
    except QuotaExceededError as exc:
        return RunSummary(
            0, 0, settings.max_billed_searches_per_run, aborted=True, note=f"circuit breaker: {exc}"
        )
    return RunSummary(len(geos), outcome.rows_written, outcome.billed_searches, False, None)


async def run_pipeline_job(
    run_id: int,
    site: str,
    mode: str,
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    now: datetime,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> RunSummary:
    """The real run job: incremental (cost-safe new geos) or full (all known geos)."""
    if mode == "full":
        return await _run_full(
            run_id, site, sessionmaker=sessionmaker, settings=settings, now=now, state_dir=state_dir
        )
    return await _run_incremental(
        run_id, site, sessionmaker=sessionmaker, settings=settings, now=now, state_dir=state_dir
    )
