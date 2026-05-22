"""Click-based CLI. Invoke via ``python -m authority_finder.cli ...``.

Currently exposes a single ``monitor`` subcommand that drives the geo_monitor
pipeline for one site or both. Per-site failures are isolated via
``asyncio.gather(return_exceptions=True)`` so a 500 from one host doesn't
stall the other. Exit code is non-zero only when *every* requested site
errored.
"""

import asyncio
import json
import sys

import click
import httpx

from authority_finder.geo_monitor.models import MonitorRun
from authority_finder.geo_monitor.monitor import run_monitor
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import SITES
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


if __name__ == "__main__":
    cli()
