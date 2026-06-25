"""Scheduler tick: per-site isolation (one site's sitemap failure must not stop the other)."""

from datetime import UTC, datetime
from pathlib import Path

from authority_finder.geo_monitor.models import GeoPage, SiteConfig, SitemapEntry
from authority_finder.scheduler.incremental import RunAndWrite
from authority_finder.scheduler.models import RunOutcome
from authority_finder.scheduler.runner import run_tick

NOW = datetime(2026, 6, 24, tzinfo=UTC)


class PerSiteSitemap:
    """Fails for MHD, returns nothing for AH — exercises per-site isolation."""

    async def fetch_all_geo_entries(self, config: SiteConfig) -> list[SitemapEntry]:
        if config.id == "mhd":
            raise RuntimeError("sitemap down")
        return []


async def test_run_tick_isolates_per_site(tmp_path: Path) -> None:
    invoked: list[str] = []

    def build(config: SiteConfig) -> RunAndWrite:
        async def _runner(_geos: list[GeoPage]) -> RunOutcome:
            invoked.append(config.id)
            return RunOutcome(rows_written=1, billed_searches=1)

        return _runner

    results = await run_tick(
        sitemap_fetcher=PerSiteSitemap(),
        build_run_and_write=build,
        now=NOW,
        state_dir=tmp_path,
    )

    by_id = {r.site_id: r for r in results}
    assert set(by_id) == {"mhd", "ah"}
    assert by_id["mhd"].aborted is True  # sitemap failure isolated to MHD
    assert by_id["ah"].aborted is False  # AH still ran
    assert by_id["ah"].new_geos_found == 0  # AH had nothing new -> no-op
    assert invoked == []  # neither site had new geos, so zero pipeline spend
