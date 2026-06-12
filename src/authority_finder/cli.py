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
from pathlib import Path
from typing import Any, cast

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
from authority_finder.page_detector.fetcher import PageFetcher
from authority_finder.page_detector.models import DetectionResult
from authority_finder.page_detector.orchestrator import detect_for_geo

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
@click.option(
    "--out",
    "out_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the JSON payload to a file (chains into `detect --in`).",
)
def discover(
    site: str,
    limit: int | None,
    level: str | None,
    refresh: bool,
    as_json: bool,
    out_file: Path | None,
) -> None:
    """Discover .gov/.edu candidate sites for known geo pages."""
    configure_logging("INFO")
    if not get_settings().serpapi_api_key.get_secret_value():
        click.echo("SERPAPI_API_KEY is not set — aborting before any search.", err=True)
        sys.exit(2)

    site_ids = list(SITES.keys()) if site == "both" else [site]
    results, billed, cached = asyncio.run(
        _run_discovery(site_ids, limit=limit, level=level, refresh=refresh)
    )

    payload = {
        "results": [r.model_dump(mode="json") for r in results],
        "billed_searches": billed,
        "cache_hits": cached,
    }
    if out_file is not None:
        out_file.write_text(json.dumps(payload, indent=2, default=str))
        click.echo(f"wrote {len(results)} discovery results to {out_file}")
    if as_json:
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


@cli.command()
@click.option(
    "--in",
    "in_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Read discovery results from a JSON file instead of running discovery.",
)
@click.option(
    "--site",
    type=click.Choice(["mhd", "ah", "both"]),
    default=None,
    help="Run discovery first (cache-aware) for these sites.",
)
@click.option("--limit", type=int, default=None, help="Max geos to process (after level filter).")
@click.option(
    "--level",
    type=click.Choice(["state", "county", "city"]),
    default=None,
    help="Only geos of this level.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit structured JSON to stdout instead of a table.",
)
@click.option(
    "--out",
    "out_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the JSON payload to a file.",
)
def detect(
    in_file: Path | None,
    site: str | None,
    limit: int | None,
    level: str | None,
    as_json: bool,
    out_file: Path | None,
) -> None:
    """Find the best outreach page for each discovered candidate."""
    configure_logging("INFO")
    if in_file is None:
        if not get_settings().serpapi_api_key.get_secret_value():
            click.echo("SERPAPI_API_KEY is not set — aborting before any search.", err=True)
            sys.exit(2)
        site = site or "both"

    results, fetches = asyncio.run(_run_detect(in_file, site=site, limit=limit, level=level))

    payload = {
        "results": [r.model_dump(mode="json") for r in results],
        "fetches_used": fetches,
    }
    if out_file is not None:
        out_file.write_text(json.dumps(payload, indent=2, default=str))
        click.echo(f"wrote {len(results)} detection results to {out_file}")
    if as_json:
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        _print_detection_table(results, fetches=fetches)

    if results and all(r.status_counts.get("detected", 0) == 0 for r in results):
        sys.exit(1)


def _load_discovery_file(path: Path) -> list[DiscoveryResult]:
    data: Any = json.loads(path.read_text())
    items = cast("list[Any]", data["results"] if isinstance(data, dict) else data)
    return [DiscoveryResult.model_validate(item) for item in items]


async def _run_detect(
    in_file: Path | None, *, site: str | None, limit: int | None, level: str | None
) -> tuple[list[DetectionResult], int]:
    if in_file is not None:
        discovery_results = _load_discovery_file(in_file)
    else:
        site_ids = list(SITES.keys()) if site == "both" else [site or "both"]
        discovery_results, _, _ = await _run_discovery(
            site_ids, limit=limit, level=level, refresh=False
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        fetcher = PageFetcher(client=client)
        results = [await detect_for_geo(d, fetcher=fetcher) for d in discovery_results]
        return results, fetcher.fetch_count


def _print_detection_table(results: list[DetectionResult], *, fetches: int) -> None:
    if not results:
        click.echo("no detection results.")
        return
    click.echo(
        f"{'geo':<58} {'det':>4} {'hi':>3} {'med':>4} {'low':>4} {'rej':>4} {'comp':>4} "
        f"{'fed':>4} {'state':>5} {'junk':>4} {'novia':>5} {'fail':>4} {'ftch':>5}"
    )
    click.echo("-" * 118)
    for r in results:
        det = r.status_counts.get("detected", 0)
        rej = r.status_counts.get("rejected", 0)
        fail = r.status_counts.get("fetch_failed", 0)
        conf = r.confidence_counts
        rejc = r.rejection_counts
        click.echo(
            f"{r.geo.url:<58} {det:>4} "
            f"{conf.get('high', 0):>3} {conf.get('medium', 0):>4} {conf.get('low', 0):>4} "
            f"{rej:>4} {rejc.get('competitor', 0):>4} {rejc.get('federal', 0):>4} "
            f"{rejc.get('wrong_state', 0):>5} {rejc.get('junk_url', 0):>4} "
            f"{rejc.get('no_viable_page', 0):>5} {fail:>4} {r.fetches_used:>5}"
        )
    click.echo(f"\nsession total: {fetches} page fetches")


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
