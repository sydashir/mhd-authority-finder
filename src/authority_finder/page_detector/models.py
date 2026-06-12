"""Data models for the page detector component.

Outcome semantics (ADR-006):

- ``detected`` — a viable page was found; confidence ``low`` means "flagged
  for manual review", not "discard".
- ``rejected`` + ``rejection_reason``:
  - ``competitor`` / ``federal`` — domain-level, decided before any fetch.
  - ``wrong_state`` — a different US state dominates the surfaced page (or
    homepage) and the target state never appears.
  - ``junk_url`` — the surfaced URL was junk (PDF, news, search, login) and
    the crawl fallback found nothing viable either.
  - ``no_viable_page`` — pages fetched and scored, none reached the
    viability floor.
- ``fetch_failed`` — nothing could be fetched at all (original and homepage).
"""

from typing import Literal

from pydantic import BaseModel

from authority_finder.discovery.models import CandidateSite, GeoRef

Confidence = Literal["high", "medium", "low"]
OutcomeStatus = Literal["detected", "rejected", "fetch_failed"]
RejectionReason = Literal["competitor", "federal", "wrong_state", "junk_url", "no_viable_page"]


class PageSignal(BaseModel):
    """One named contribution to a page's score — every score must decompose."""

    name: str
    weight_contribution: float
    detail: str


class DetectedPage(BaseModel):
    """The best page found on a candidate domain, with its score breakdown."""

    url: str
    score: float
    confidence: Confidence
    signals: list[PageSignal]
    state_validated: bool
    fetched_ok: bool = True


class CandidateOutcome(BaseModel):
    """Detection outcome for one discovery candidate."""

    candidate: CandidateSite
    status: OutcomeStatus
    rejection_reason: RejectionReason | None = None
    detected: DetectedPage | None = None
    fetches_used: int = 0


class DetectionResult(BaseModel):
    """Detection outcomes for one geo's full candidate list."""

    geo: GeoRef
    outcomes: list[CandidateOutcome] = []
    status_counts: dict[OutcomeStatus, int] = {}
    rejection_counts: dict[RejectionReason, int] = {}
    confidence_counts: dict[Confidence, int] = {}
    fetches_used: int = 0
