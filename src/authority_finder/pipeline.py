"""Full Phase-1 pipeline: discover → detect → extract → populate → assemble.

One geo's failure is isolated (discover/detect/extract already isolate per
candidate; the per-geo block is additionally guarded) so a single bad geo never
voids the batch. Population is looked up once per geo and shared across its
rows. Writing (CSV or Sheets) is the caller's job — this returns the assembled
:class:`OutputRow`s plus a funnel summary.
"""

import asyncio
from datetime import datetime

import structlog
from pydantic import BaseModel

from authority_finder.authority_filter.ahrefs_client import AhrefsClient
from authority_finder.authority_filter.discover import authority_candidates_for_geo
from authority_finder.contact_extractor.models import ExtractionResult
from authority_finder.contact_extractor.orchestrator import extract_for_geo
from authority_finder.discovery.discover import discover_many
from authority_finder.discovery.models import GeoRef
from authority_finder.discovery.serpapi_client import SerpApiClient
from authority_finder.fetching import PageFetcher
from authority_finder.fetching.models import FetchTier
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.link_checker.models import LinkCheckResult
from authority_finder.link_checker.orchestrator import check_links_for_candidate
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
    rows_with_competitor_links: int
    competitor_links_found: int
    fetches_used: int
    fetch_tiers: dict[FetchTier, int]
    billed_searches: int


async def _check_links(
    extraction: ExtractionResult, *, fetcher: PageFetcher
) -> list[LinkCheckResult]:
    """Competitor link check for every detected page in one geo, per-candidate isolated."""
    raw = await asyncio.gather(
        *(
            check_links_for_candidate(o.candidate, o.page_url, fetcher=fetcher)
            for o in extraction.outcomes
        ),
        return_exceptions=True,
    )
    results: list[LinkCheckResult] = []
    for outcome, result in zip(extraction.outcomes, raw, strict=True):
        if isinstance(result, BaseException):
            _log.error(
                "pipeline.linkcheck_failed",
                domain=outcome.candidate.registrable_domain,
                error=str(result),
            )
            results.append(
                LinkCheckResult(
                    candidate=outcome.candidate, checked_ok=False, note="linkcheck error"
                )
            )
        else:
            results.append(result)
    return results


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
    ahrefs_client: AhrefsClient | None = None,
) -> tuple[list[OutputRow], PipelineFunnel]:
    """Run the full chain over geos; return assembled rows + a funnel summary.

    When ``ahrefs_client`` is supplied, component 3's unrestricted authority candidates are
    merged into each geo's discovery result BEFORE detection, so they run the identical
    downstream gates as .gov/.edu candidates. Absent it, the pipeline is unchanged.
    """
    _log.info("pipeline.start", geos=len(geos))
    discovery_results = await discover_many(geos, client=serp_client)

    authority_added = 0
    if ahrefs_client is not None:
        by_url = {g.url: g for g in geos}
        for discovery in discovery_results:
            geo_page = by_url.get(discovery.geo.url)
            if geo_page is None:
                continue
            try:
                extra, _ratings = await authority_candidates_for_geo(
                    geo_page, serp_client=serp_client, ahrefs_client=ahrefs_client, now=now
                )
            except Exception as exc:
                _log.error("pipeline.authority_failed", geo=discovery.geo.url, error=str(exc))
                continue
            known = {c.registrable_domain for c in discovery.candidates}
            fresh = [c for c in extra if c.registrable_domain not in known]
            discovery.candidates.extend(fresh)
            authority_added += len(fresh)
        _log.info("pipeline.authority_merged", added=authority_added)

    rows: list[OutputRow] = []
    candidates = detected = with_email = with_phone = population_found = 0
    competitor_rows = competitor_links_total = 0
    for discovery in discovery_results:
        candidates += len(discovery.candidates)
        try:
            detection = await detect_for_geo(discovery, fetcher=fetcher)
            extraction = await extract_for_geo(detection, fetcher=fetcher)
            population = await census_client.population_for(_geo_page(discovery.geo, now=now))
            link_results = await _check_links(extraction, fetcher=fetcher)
        except Exception as exc:
            # Isolate one geo's failure so the batch goes on.
            _log.error("pipeline.geo_failed", geo=discovery.geo.url, error=str(exc))
            continue

        detected += len(extraction.outcomes)
        with_email += extraction.with_email
        with_phone += extraction.with_phone
        for outcome, link_result in zip(extraction.outcomes, link_results, strict=True):
            cell = "; ".join(link_result.competitor_domains) or "—"
            row = build_row(outcome, population=population, now=now, competitor_links=cell)
            rows.append(row)
            if row.population is not None:
                population_found += 1
            if link_result.links_found:
                competitor_rows += 1
                competitor_links_total += len(link_result.links_found)

    funnel = PipelineFunnel(
        geos=len(discovery_results),
        candidates=candidates,
        detected=detected,
        with_email=with_email,
        with_phone=with_phone,
        rows=len(rows),
        population_found=population_found,
        rows_with_competitor_links=competitor_rows,
        competitor_links_found=competitor_links_total,
        fetches_used=fetcher.fetch_count,
        fetch_tiers=dict(fetcher.tier_counts),
        billed_searches=serp_client.billed_search_count,
    )
    _log.info("pipeline.finish", **funnel.model_dump())
    return rows, funnel
