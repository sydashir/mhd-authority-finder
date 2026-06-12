"""Click-based CLI. Invoke via ``python -m authority_finder.cli ...``.

``monitor`` drives the geo_monitor pipeline for one site or both; ``discover``
runs SerpAPI discovery against the geos already persisted in
``data/state/{site}.json``. Failures are isolated per site / per geo so one
bad host doesn't stall the rest. Exit code is non-zero only when *every*
requested unit errored.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime

import click
import httpx

from authority_finder.config import get_settings
from authority_finder.discovery.discover import discover_many
from authority_finder.discovery.models import DiscoveryResult
from authority_finder.discovery.serpapi_client import SerpApiClient
from authority_finder.geo_monitor.models import GeoPage, MonitorRun
from authority_finder.geo_monitor.monitor import run_monitor
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import SITES
from authority_finder.geo_monitor.state import load_state
from authority_finder.geo_monitor.url_parser import parse_geo_url
from authority_finder.logging import configure as configure_logging

SiteFailure = tuple[str, str]


@click.group()
def cli() -> None:
    """authority-finder CLI."""


@cli.command()
@click.option(
    "--site",
    type=click.Choice(["mhd", "ah", "both"]),
    default="both",
    show_default=True,
    help="Which site to poll.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit structured JSON to stdout instead of a table.",
)
def monitor(site: str, as_json: bool) -> None:
    """Discover newly-added geo pages on MHD, AH, or both."""
    configure_logging("INFO")
    site_ids = list(SITES.keys()) if site == "both" else [site]

    runs, failures = asyncio.run(_run_sites(site_ids))

    if as_json:
        payload = {
            "runs": [r.model_dump(mode="json") for r in runs],
            "failures": [{"site_id": sid, "error": err} for sid, err in failures],
        }
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        _print_table(runs, failures)

    if failures and not runs:
        sys.exit(1)


async def _run_sites(site_ids: list[str]) -> tuple[list[MonitorRun], list[SiteFailure]]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        coros = [run_monitor(SITES[sid], fetcher=SitemapFetcher(client=client)) for sid in site_ids]
        results = await asyncio.gather(*coros, return_exceptions=True)

    runs: list[MonitorRun] = []
    failures: list[SiteFailure] = []
    for sid, result in zip(site_ids, results, strict=True):
        if isinstance(result, BaseException):
            failures.append((sid, str(result)))
        else:
            runs.append(result)
    return runs, failures


def _print_table(runs: list[MonitorRun], failures: list[SiteFailure]) -> None:
    if not runs and not failures:
        click.echo("no sites monitored.")
        return

    click.echo(f"{'site':<6} {'total':>6} {'new':>5} {'state':>6} {'county':>7} {'city':>5}")
    click.echo("-" * 42)
    for run in runs:
        by_level = {"state": 0, "county": 0, "city": 0}
        for page in run.new_pages:
            by_level[page.level] += 1
        click.echo(
            f"{run.site_id:<6} {run.total_pages:>6} {len(run.new_pages):>5} "
            f"{by_level['state']:>6} {by_level['county']:>7} {by_level['city']:>5}"
        )
    for sid, err in failures:
        click.echo(f"{sid:<6} FAILED  {err}")


@cli.command()
@click.option(
    "--site",
    type=click.Choice(["mhd", "ah", "both"]),
    default="both",
    show_default=True,
    help="Whose known geos to discover for.",
)
@click.option("--limit", type=int, default=None, help="Max geos to process (after level filter).")
@click.option(
    "--level",
    type=click.Choice(["state", "county", "city"]),
    default=None,
    help="Only geos of this level.",
)
@click.option(
    "--refresh",
    is_flag=True,
    default=False,
    help="Re-run the sitemap monitor before discovery.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit structured JSON to stdout instead of a table.",
)
def discover(site: str, limit: int | None, level: str | None, refresh: bool, as_json: bool) -> None:
    """Discover .gov/.edu candidate sites for known geo pages."""
    configure_logging("INFO")
    if not get_settings().serpapi_api_key.get_secret_value():
        click.echo("SERPAPI_API_KEY is not set — aborting before any search.", err=True)
        sys.exit(2)

    site_ids = list(SITES.keys()) if site == "both" else [site]
    results, billed, cached = asyncio.run(
        _run_discovery(site_ids, limit=limit, level=level, refresh=refresh)
    )

    if as_json:
        payload = {
            "results": [r.model_dump(mode="json") for r in results],
            "billed_searches": billed,
            "cache_hits": cached,
        }
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        _print_discovery_table(results, billed=billed, cached=cached)

    if not results:
        click.echo("no geos matched the filters.")
        return
    if all(r.errors and not r.candidates for r in results):
        sys.exit(1)


async def _run_discovery(
    site_ids: list[str], *, limit: int | None, level: str | None, refresh: bool
) -> tuple[list[DiscoveryResult], int, int]:
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        if refresh:
            for sid in site_ids:
                await run_monitor(SITES[sid], fetcher=SitemapFetcher(client=http_client))

        now = datetime.now(UTC)
        geos: list[GeoPage] = []
        for sid in site_ids:
            state = load_state(sid)
            for url in sorted(state.known_urls):
                page = parse_geo_url(url, SITES[sid], now=now)
                if page is not None:
                    geos.append(page)
        if level is not None:
            geos = [g for g in geos if g.level == level]
        if limit is not None:
            geos = geos[:limit]

        serp = SerpApiClient(client=http_client, api_key=get_settings().serpapi_api_key)
        results = await discover_many(geos, client=serp)
        return results, serp.billed_search_count, serp.cache_hit_count


def _print_discovery_table(results: list[DiscoveryResult], *, billed: int, cached: int) -> None:
    if not results:
        return
    click.echo(
        f"{'geo':<58} {'lvl':<6} {'cand':>4} {'gov':>4} {'edu':>4} "
        f"{'us':>3} {'other':>5} {'billed':>6} {'cached':>6} {'errs':>4}"
    )
    click.echo("-" * 110)
    for r in results:
        counts = {"gov": 0, "edu": 0, "us_local": 0, "other": 0} | dict(r.counts_by_class)
        geo_cached = r.queries_run - r.billed_searches - len(r.errors)
        click.echo(
            f"{r.geo.url:<58} {r.geo.level:<6} {len(r.candidates):>4} "
            f"{counts['gov']:>4} {counts['edu']:>4} {counts['us_local']:>3} "
            f"{counts['other']:>5} {r.billed_searches:>6} {geo_cached:>6} {len(r.errors):>4}"
        )
    click.echo(f"\nsession totals: {billed} billed searches, {cached} cache hits")


if __name__ == "__main__":
    cli()
