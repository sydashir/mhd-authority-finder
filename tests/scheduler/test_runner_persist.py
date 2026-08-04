"""The scheduler's pipeline closure must persist to Postgres, not just the Sheet (ADR-025).

Before this fix the Docker scheduler wrote the Google Sheet only, so a 3am-discovered
prospect never reached the DB the dashboard reads — a split-brain. These prove the closure
now upserts prospects + records a run, and preserves user outreach fields on re-run (ADR-022).
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from authority_finder.config import get_settings
from authority_finder.db import repository as repo
from authority_finder.db.models import OutreachStatus
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.output.models import OutputRow
from authority_finder.output.sheets_writer import SheetsWriteResult
from authority_finder.pipeline import PipelineFunnel
from authority_finder.scheduler import runner

# Deliberately reaching for the private closure factory: it IS the unit under test.
from authority_finder.scheduler.runner import (
    _make_run_and_write,  # pyright: ignore[reportPrivateUsage]
)

NOW = datetime(2026, 7, 22, tzinfo=UTC)


def _geo() -> GeoPage:
    return GeoPage(
        url="https://addictionhotline.com/wyoming/",
        site_id="ah",
        state="wyoming",
        county=None,
        city=None,
        level="state",
        first_seen=NOW,
    )


def _row(domain: str, *, trust: str = "high") -> OutputRow:
    return OutputRow(
        website=domain,
        specific_page=f"https://{domain}/counseling",
        email=f"c@{domain}",
        phone="",
        contact_source="mailto (same-domain)",
        contact_trust=trust,
        organization_description="",
        geo_served="Wyoming",
        population=584057,
        competitor_links="—",
        source_tag="AH",
        date_added="2026-07-22",
        confidence="high",
    )


def _funnel() -> PipelineFunnel:
    return PipelineFunnel(
        geos=1,
        candidates=2,
        detected=2,
        with_email=2,
        with_phone=0,
        rows=2,
        population_found=2,
        rows_with_competitor_links=0,
        competitor_links_found=0,
        fetches_used=4,
        fetch_tiers={},
        billed_searches=3,
    )


class _FakeBrowser:
    def __init__(self, **_kw: Any) -> None: ...
    async def aclose(self) -> None: ...


class _FakeWriter:
    def __init__(self, **_kw: Any) -> None: ...
    async def write(self, rows: list[OutputRow], **_kw: Any) -> SheetsWriteResult:
        return SheetsWriteResult(appended=len(rows), skipped_existing=0, header_written=False)


@pytest.fixture(name="_patched")
def patched_runner(monkeypatch: pytest.MonkeyPatch) -> list[OutputRow]:
    rows = [_row("uwyo.edu"), _row("wyo.gov", trust="low")]

    async def fake_pipeline(
        _geos: list[GeoPage], **_kw: Any
    ) -> tuple[list[OutputRow], PipelineFunnel]:
        return rows, _funnel()

    monkeypatch.setattr(runner, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(runner, "SheetsWriter", _FakeWriter)
    monkeypatch.setattr(runner, "PlaywrightBrowserFetcher", _FakeBrowser)
    return rows


async def test_scheduler_closure_persists_prospects_and_run(
    session_factory: async_sessionmaker[AsyncSession], _patched: list[OutputRow]
) -> None:
    closure = _make_run_and_write(
        settings=get_settings(), now=NOW, sessionmaker=session_factory, site="ah"
    )
    outcome = await closure([_geo()])

    assert outcome.rows_written == 2
    assert outcome.billed_searches == 3
    async with session_factory() as s:
        assert await repo.count_prospects(s) == 2  # reached Postgres, not just the Sheet
        runs = await repo.get_runs(s)
        assert len(runs) == 1 and runs[0].billed_searches == 3


async def test_scheduler_rerun_preserves_outreach(
    session_factory: async_sessionmaker[AsyncSession], _patched: list[OutputRow]
) -> None:
    closure = _make_run_and_write(
        settings=get_settings(), now=NOW, sessionmaker=session_factory, site="ah"
    )
    await closure([_geo()])
    # A teammate marks one prospect contacted...
    async with session_factory() as s:
        await s.execute(
            text(
                "UPDATE prospects SET outreach_status='contacted', outreach_notes='called' "
                "WHERE website='uwyo.edu'"
            )
        )
        await s.commit()
    # ...a later scheduled tick re-processes the same geo — must NOT clobber the note.
    await closure([_geo()])
    async with session_factory() as s:
        rows = await repo.get_prospects(s)
        assert len(rows) == 2  # upsert, not duplicate
        contacted = next(r for r in rows if r.website == "uwyo.edu")
        assert contacted.outreach_status is OutreachStatus.contacted
        assert contacted.outreach_notes == "called"
