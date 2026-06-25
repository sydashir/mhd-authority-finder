"""Incremental run mode — the cost-safety core (ADR-012).

Non-negotiable: zero new geos => zero SerpAPI spend and zero writes; a crash
mid-run must NOT mark geos seen (so they retry next tick); state is persisted
only after a successful run, and only for the geos actually processed.
"""

from datetime import UTC, datetime
from pathlib import Path

from authority_finder.geo_monitor.models import GeoPage, SiteConfig, SitemapEntry, SiteState
from authority_finder.geo_monitor.sites import MHD
from authority_finder.geo_monitor.state import load_state, save_state
from authority_finder.scheduler.incremental import run_incremental
from authority_finder.scheduler.models import RunOutcome

NOW = datetime(2026, 6, 24, tzinfo=UTC)
BASE = "https://inpatientmentalhealthfinder.com"
FL = f"{BASE}/serving/florida/"
CA = f"{BASE}/serving/california/"
CO = f"{BASE}/serving/colorado/"
_DEFAULT_OUTCOME = RunOutcome(rows_written=3, billed_searches=4)


class FakeSitemap:
    def __init__(self, locs: list[str]) -> None:
        self._locs = locs

    async def fetch_all_geo_entries(self, config: SiteConfig) -> list[SitemapEntry]:  # noqa: ARG002
        return [SitemapEntry(loc=loc) for loc in self._locs]


class RecordingRunner:
    def __init__(self, outcome: RunOutcome = _DEFAULT_OUTCOME) -> None:
        self.calls: list[list[str]] = []
        self._outcome = outcome

    async def __call__(self, geos: list[GeoPage]) -> RunOutcome:
        self.calls.append([g.url for g in geos])
        return self._outcome


async def test_zero_new_geos_is_noop(tmp_path: Path) -> None:
    save_state("mhd", SiteState(known_urls={FL, CA}), state_dir=tmp_path)
    runner = RecordingRunner()
    result = await run_incremental(
        MHD,
        sitemap_fetcher=FakeSitemap([FL, CA]),
        run_and_write=runner,
        now=NOW,
        state_dir=tmp_path,
    )
    assert result.new_geos_found == 0
    assert result.processed == 0
    assert result.rows_written == 0
    assert result.billed_searches == 0
    assert runner.calls == []  # pipeline never invoked => zero spend, zero writes
    assert load_state("mhd", state_dir=tmp_path).known_urls == {FL, CA}


async def test_new_geos_processed_and_state_saved(tmp_path: Path) -> None:
    save_state("mhd", SiteState(known_urls={FL}), state_dir=tmp_path)
    runner = RecordingRunner(RunOutcome(rows_written=5, billed_searches=8))
    result = await run_incremental(
        MHD,
        sitemap_fetcher=FakeSitemap([FL, CA, CO]),
        run_and_write=runner,
        now=NOW,
        state_dir=tmp_path,
    )
    assert result.new_geos_found == 2
    assert result.processed == 2
    assert result.rows_written == 5
    assert result.billed_searches == 8
    assert sorted(runner.calls[0]) == sorted([CA, CO])  # only the 2 NEW geos processed
    assert load_state("mhd", state_dir=tmp_path).known_urls == {FL, CA, CO}


async def test_crash_does_not_save_state(tmp_path: Path) -> None:
    save_state("mhd", SiteState(known_urls={FL}), state_dir=tmp_path)

    async def boom(_geos: list[GeoPage]) -> RunOutcome:
        raise RuntimeError("pipeline blew up")

    result = await run_incremental(
        MHD, sitemap_fetcher=FakeSitemap([FL, CA]), run_and_write=boom, now=NOW, state_dir=tmp_path
    )
    assert result.aborted is True
    assert result.processed == 0
    # CA must NOT be marked seen — a crash mid-run retries next tick.
    assert load_state("mhd", state_dir=tmp_path).known_urls == {FL}
