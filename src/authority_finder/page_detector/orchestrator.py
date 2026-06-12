"""Geo-level detection orchestration.

All candidates for a geo run concurrently — actual HTTP concurrency is capped
by the fetcher's global and per-host semaphores, so gathering wide here is
safe. A candidate whose pipeline raises unexpectedly becomes a
``fetch_failed`` outcome rather than killing the geo.
"""

import asyncio

import structlog

from authority_finder.discovery.models import DiscoveryResult
from authority_finder.page_detector.detector import process_candidate
from authority_finder.page_detector.fetcher import PageFetcher
from authority_finder.page_detector.models import (
    CandidateOutcome,
    Confidence,
    DetectionResult,
    OutcomeStatus,
    RejectionReason,
)

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def detect_for_geo(discovery: DiscoveryResult, *, fetcher: PageFetcher) -> DetectionResult:
    """Run page detection for every candidate in one geo's discovery result."""
    geo = discovery.geo
    _log.info("detect.start", geo=geo.url, candidates=len(discovery.candidates))

    raw = await asyncio.gather(
        *(process_candidate(c, geo=geo, fetcher=fetcher) for c in discovery.candidates),
        return_exceptions=True,
    )

    outcomes: list[CandidateOutcome] = []
    for candidate, result in zip(discovery.candidates, raw, strict=True):
        if isinstance(result, BaseException):
            _log.error(
                "detect.candidate_failed",
                candidate=candidate.registrable_domain,
                error=str(result),
            )
            outcomes.append(CandidateOutcome(candidate=candidate, status="fetch_failed"))
        else:
            outcomes.append(result)

    status_counts: dict[OutcomeStatus, int] = {}
    rejection_counts: dict[RejectionReason, int] = {}
    confidence_counts: dict[Confidence, int] = {}
    fetches = 0
    for outcome in outcomes:
        status_counts[outcome.status] = status_counts.get(outcome.status, 0) + 1
        if outcome.rejection_reason is not None:
            reason = outcome.rejection_reason
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        if outcome.detected is not None:
            band = outcome.detected.confidence
            confidence_counts[band] = confidence_counts.get(band, 0) + 1
        fetches += outcome.fetches_used

    _log.info(
        "detect.finish",
        geo=geo.url,
        status_counts=dict(status_counts),
        confidence_counts=dict(confidence_counts),
        fetches_used=fetches,
    )
    return DetectionResult(
        geo=geo,
        outcomes=outcomes,
        status_counts=status_counts,
        rejection_counts=rejection_counts,
        confidence_counts=confidence_counts,
        fetches_used=fetches,
    )
