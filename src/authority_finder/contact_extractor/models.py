"""Data models for the contact extractor (ADR-007).

Direct-scrape only (ADR-003). Every hit carries its source and a context
snippet so a human can QA the row without re-fetching the page — a wrong
contact is worse than no contact, so provenance is first-class.
"""

from typing import Literal

from pydantic import BaseModel

from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.fetching.models import FetchTier
from authority_finder.page_detector.models import Confidence

EmailSource = Literal["mailto", "body_text", "contact_page"]
PhoneSource = Literal["tel", "body_text", "contact_page"]
ExtractionStatus = Literal["extracted", "partial", "none", "fetch_failed"]


class EmailHit(BaseModel):
    """One extracted email with provenance and a confidence in [0, 1].

    ``same_domain`` = the email's registrable domain matches the page it was found
    on. Body-text emails are kept only when same-domain (third-party orgs mentioned
    on a page are not that page's contact); mailto/contact-page hits keep the flag
    for trust banding but are not dropped on it.
    """

    address: str
    source: EmailSource
    context: str = ""
    confidence: float
    same_domain: bool = True


class PhoneHit(BaseModel):
    """One extracted phone: E.164 where the number validated, plus the raw match."""

    number: str | None
    raw: str
    source: PhoneSource
    context: str = ""


class ContactSet(BaseModel):
    """All contacts found for one page, ranked best-first within each list."""

    emails: list[EmailHit] = []
    phones: list[PhoneHit] = []
    best_email: str | None = None
    best_phone: str | None = None
    contact_page_url: str | None = None
    has_contact_form: bool = False
    notes: str = ""


class ExtractionOutcome(BaseModel):
    """Contact extraction result for one detected candidate page."""

    candidate: CandidateSite
    page_url: str
    page_confidence: Confidence
    status: ExtractionStatus
    contacts: ContactSet = ContactSet()
    fetches_used: int = 0


class ExtractionResult(BaseModel):
    """Contact extraction across one geo's detected pages."""

    geo: GeoRef
    outcomes: list[ExtractionOutcome] = []
    status_counts: dict[ExtractionStatus, int] = {}
    with_email: int = 0
    with_phone: int = 0
    form_only: int = 0
    fetch_tiers: dict[FetchTier, int] = {}
    fetches_used: int = 0
