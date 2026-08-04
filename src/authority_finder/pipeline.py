"""Full Phase-1 pipeline: discover → detect → extract → populate → assemble.

One geo's failure is isolated (discover/detect/extract already isolate per
candidate; the per-geo block is additionally guarded) so a single bad geo never
voids the batch. Population is looked up once per geo and shared across its
rows. Writing (CSV or Sheets) is the caller's job — this returns the assembled
:class:`OutputRow`s plus a funnel summary.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from authority_finder.authority_filter.ahrefs_client import AhrefsClient
from authority_finder.authority_filter.discover import authority_candidates_for_geo
from authority_finder.contact_extractor.models import ExtractionResult
from authority_finder.contact_extractor.orchestrator import extract_for_geo
from authority_finder.discovery.discover import discover_many
from authority_finder.discovery.models import DiscoveryResult, GeoRef
from authority_finder.discovery.serpapi_client import SerpApiClient
from authority_finder.fetching import PageFetcher
from authority_finder.fetching.models import FetchTier
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.link_checker.models import LinkCheckResult
from authority_finder.link_checker.orchestrator import check_links_for_candidate
from authority_finder.output.blocked_writer import BlockedCandidate, collect_blocked
from authority_finder.output.models import OutputRow, build_row
from authority_finder.page_detector.orchestrator import detect_for_geo
from authority_finder.population.census import CensusClient

if TYPE_CHECKING:
    from authority_finder.page_detector.models import DetectionResult

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
    # Real orgs the tool could not reach (CAPTCHA / hard 403) but a person can. Surfaced,
    # never silently dropped — ncala.org, the brief's own example, is exactly this case.
    blocked: list[BlockedCandidate] = []


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


async def _merge_authority_candidates(
    discovery_results: list[DiscoveryResult],
    *,
    geos: list[GeoPage],
    serp_client: SerpApiClient,
    ahrefs_client: AhrefsClient | None,
    now: datetime,
) -> dict[str, float]:
    """Merge component 3's authority candidates into each geo's discovery result, in place.

    Emitting ordinary ``CandidateSite`` objects and merging them BEFORE detection is what makes
    gate reuse structural (ADR-027): there is no second code path that could skip a gate.
    Returns the Domain Ratings so row assembly can carry them — they were being computed and
    discarded before.
    """
    if ahrefs_client is None:
        return {}

    domain_ratings: dict[str, float] = {}
    added = 0
    by_url = {g.url: g for g in geos}
    for discovery in discovery_results:
        geo_page = by_url.get(discovery.geo.url)
        if geo_page is None:
            continue
        try:
            extra, ratings = await authority_candidates_for_geo(
                geo_page, serp_client=serp_client, ahrefs_client=ahrefs_client, now=now
            )
        except Exception as exc:  # one geo's authority failure must not lose the batch
            _log.error("pipeline.authority_failed", geo=discovery.geo.url, error=str(exc))
            continue
        known = {c.registrable_domain for c in discovery.candidates}
        fresh = [c for c in extra if c.registrable_domain not in known]
        discovery.candidates.extend(fresh)
        added += len(fresh)
        for domain, rating in ratings.items():
            if rating.dr is not None:
                domain_ratings[domain] = rating.dr
    _log.info("pipeline.authority_merged", added=added)
    return domain_ratings


async def run_pipeline(
    geos: list[GeoPage],
    *,
    serp_client: SerpApiClient,
    fetcher: PageFetcher,
    census_client: CensusClient,
    now: datetime,
    ahrefs_client: AhrefsClient | None = None,
    on_geo_rows: Callable[[GeoRef, list[OutputRow]], None] | None = None,
) -> tuple[list[OutputRow], PipelineFunnel]:
    """Run the full chain over geos; return assembled rows + a funnel summary.

    When ``ahrefs_client`` is supplied, component 3's unrestricted authority candidates are
    merged into each geo's discovery result BEFORE detection, so they run the identical
    downstream gates as .gov/.edu candidates. Absent it, the pipeline is unchanged.
    """
    _log.info("pipeline.start", geos=len(geos))
    discovery_results = await discover_many(geos, client=serp_client)

    domain_ratings = await _merge_authority_candidates(
        discovery_results,
        geos=geos,
        serp_client=serp_client,
        ahrefs_client=ahrefs_client,
        now=now,
    )

    rows: list[OutputRow] = []
    detections: list[DetectionResult] = []
    candidates = detected = with_email = with_phone = population_found = 0
    competitor_rows = competitor_links_total = 0
    for discovery in discovery_results:
        candidates += len(discovery.candidates)
        try:
            detection = await detect_for_geo(discovery, fetcher=fetcher)
            detections.append(detection)
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
        geo_rows: list[OutputRow] = []
        for outcome, link_result in zip(extraction.outcomes, link_results, strict=True):
            cell = "; ".join(link_result.competitor_domains) or "—"
            row = build_row(
                outcome,
                population=population,
                now=now,
                competitor_links=cell,
                domain_rating=domain_ratings.get(outcome.candidate.registrable_domain),
                # Blank when the links are on the contact page itself; populated only when
                # the resources hop is where they actually live (ADR-011).
                competitor_links_found_on="; ".join(
                    link_result.found_on_pages(exclude=outcome.page_url)
                ),
            )
            rows.append(row)
            geo_rows.append(row)
            if row.population is not None:
                population_found += 1
            if link_result.links_found:
                competitor_rows += 1
                competitor_links_total += len(link_result.links_found)

        if on_geo_rows is not None:
            try:
                on_geo_rows(discovery.geo, geo_rows)
            except Exception as exc:  # a checkpoint failure must never lose the run
                _log.error("pipeline.checkpoint_failed", geo=discovery.geo.url, error=str(exc))

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
        blocked=collect_blocked(detections),
    )
    _log.info("pipeline.finish", **funnel.model_dump())
    return rows, funnel
