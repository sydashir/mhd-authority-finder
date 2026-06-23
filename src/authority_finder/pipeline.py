"""Full Phase-1 pipeline: discover → detect → extract → populate → assemble.

One geo's failure is isolated (discover/detect/extract already isolate per
candidate; the per-geo block is additionally guarded) so a single bad geo never
voids the batch. Population is looked up once per geo and shared across its
rows. Writing (CSV or Sheets) is the caller's job — this returns the assembled
:class:`OutputRow`s plus a funnel summary.
"""

from datetime import datetime

import structlog
from pydantic import BaseModel

from authority_finder.contact_extractor.orchestrator import extract_for_geo
from authority_finder.discovery.discover import discover_many
from authority_finder.discovery.models import GeoRef
from authority_finder.discovery.serpapi_client import SerpApiClient
from authority_finder.fetching import PageFetcher
from authority_finder.fetching.models import FetchTier
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.output.models import OutputRow, build_row
from authority_finder.page_detector.orchestrator import detect_for_geo
from authority_finder.population.census import CensusClient

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PipelineFunnel(BaseModel):
    """Stage-by-stage counts for one pipeline run."""

    geos: int
    candidates: int
    detected: int
    with_email: int
    with_phone: int
    rows: int
    population_found: int
    fetches_used: int
    fetch_tiers: dict[FetchTier, int]
    billed_searches: int


def _geo_page(ref: GeoRef, *, now: datetime) -> GeoPage:
    return GeoPage(
        url=ref.url,
        site_id=ref.site_id,
        state=ref.state,
        county=ref.county,
        city=ref.city,
        level=ref.level,
        first_seen=now,
    )


async def run_pipeline(
    geos: list[GeoPage],
    *,
    serp_client: SerpApiClient,
    fetcher: PageFetcher,
    census_client: CensusClient,
    now: datetime,
) -> tuple[list[OutputRow], PipelineFunnel]:
    """Run the full chain over geos; return assembled rows + a funnel summary."""
    _log.info("pipeline.start", geos=len(geos))
    discovery_results = await discover_many(geos, client=serp_client)

    rows: list[OutputRow] = []
    candidates = detected = with_email = with_phone = population_found = 0
    for discovery in discovery_results:
        candidates += len(discovery.candidates)
        try:
            detection = await detect_for_geo(discovery, fetcher=fetcher)
            extraction = await extract_for_geo(detection, fetcher=fetcher)
            population = await census_client.population_for(_geo_page(discovery.geo, now=now))
        except Exception as exc:
            # Isolate one geo's failure so the batch goes on.
            _log.error("pipeline.geo_failed", geo=discovery.geo.url, error=str(exc))
            continue

        detected += len(extraction.outcomes)
        with_email += extraction.with_email
        with_phone += extraction.with_phone
        for outcome in extraction.outcomes:
            row = build_row(outcome, population=population, now=now)
            rows.append(row)
            if row.population is not None:
                population_found += 1

    funnel = PipelineFunnel(
        geos=len(discovery_results),
        candidates=candidates,
        detected=detected,
        with_email=with_email,
        with_phone=with_phone,
        rows=len(rows),
        population_found=population_found,
        fetches_used=fetcher.fetch_count,
        fetch_tiers=dict(fetcher.tier_counts),
        billed_searches=serp_client.billed_search_count,
    )
    _log.info("pipeline.finish", **funnel.model_dump())
    return rows, funnel
