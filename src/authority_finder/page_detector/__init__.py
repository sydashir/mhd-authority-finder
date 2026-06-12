"""Pick the specific department / resource page on a discovered domain.

The outreach team wants the probation-resources or behavioral-health page,
not the county homepage. Candidates are pre-filtered (competitor / federal /
junk URLs), the surfaced page is fetched and scored on named signals, and a
bounded same-domain crawl fallback hunts for a better page when the surfaced
one is junk or weak. Rows below the confidence threshold are flagged for
manual review rather than dropped.
"""

from authority_finder.page_detector.models import (
    CandidateOutcome,
    Confidence,
    DetectedPage,
    DetectionResult,
    OutcomeStatus,
    PageSignal,
    RejectionReason,
)

__all__ = [
    "CandidateOutcome",
    "Confidence",
    "DetectedPage",
    "DetectionResult",
    "OutcomeStatus",
    "PageSignal",
    "RejectionReason",
]
