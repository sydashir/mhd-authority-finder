"""Contact extraction orchestration over a geo's detected pages.

Per detected candidate: fetch the page (shared tier, so 403/SSL escalates to
Playwright), extract email + phone; if no email, follow up to
:data:`MAX_CONTACT_FETCHES` ranked same-domain contact pages and extract there
too. A contact page reached by redirect off the candidate's domain is ignored
(the detector's palmerlakerecovery.com lesson). A page that only offers an
input form (no email/phone) is recorded as ``partial`` — still outreach intel.
"""

import asyncio
from typing import TYPE_CHECKING

import structlog

from authority_finder.contact_extractor.contact_page import find_contact_links
from authority_finder.contact_extractor.extract import (
    extract_emails,
    extract_phones,
    rank_emails,
    rank_phones,
)
from authority_finder.contact_extractor.models import (
    ContactSet,
    ExtractionOutcome,
    ExtractionResult,
    ExtractionStatus,
)
from authority_finder.discovery.classify import registrable_domain
from authority_finder.fetching import FetchError, PageContent, PageFetcher
from authority_finder.page_detector.models import CandidateOutcome, DetectionResult
from authority_finder.robots import RobotsDisallowedError

if TYPE_CHECKING:
    from authority_finder.fetching.models import FetchTier

MAX_CONTACT_FETCHES = 2

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _safe_fetch(fetcher: PageFetcher, url: str) -> PageContent | None:
    try:
        return await fetcher.fetch(url)
    except (FetchError, RobotsDisallowedError) as exc:
        _log.debug("extract.fetch_failed", url=url, error=str(exc))
        return None


async def extract_candidate(
    outcome: CandidateOutcome, *, fetcher: PageFetcher
) -> ExtractionOutcome:
    """Extract contacts for one detected candidate page (+ bounded contact-page hop)."""
    detected = outcome.detected
    if detected is None:
        raise ValueError("extract_candidate requires a detected page")
    url = detected.url
    domain = registrable_domain(url)

    base = ExtractionOutcome(
        candidate=outcome.candidate,
        page_url=url,
        page_confidence=detected.confidence,
        status="none",
    )

    content = await _safe_fetch(fetcher, url)
    if content is None:
        return base.model_copy(update={"status": "fetch_failed", "fetches_used": 1})

    fetches = 1
    emails = extract_emails(content)
    phones = extract_phones(content)
    has_form = content.has_web_form
    contact_page_url: str | None = None

    if not emails:
        for link in find_contact_links(content, domain=domain, limit=MAX_CONTACT_FETCHES):
            if fetches >= 1 + MAX_CONTACT_FETCHES:
                break
            cp = await _safe_fetch(fetcher, link)
            fetches += 1
            if cp is None or registrable_domain(cp.final_url) != domain:
                continue
            if contact_page_url is None:
                contact_page_url = cp.final_url
            emails.extend(extract_emails(cp, contact_page=True))
            phones.extend(extract_phones(cp, contact_page=True))
            has_form = has_form or cp.has_web_form
            if emails:
                break

    ranked_emails = rank_emails(emails)
    ranked_phones = rank_phones(phones)
    has_contact_form = has_form and not ranked_emails
    contacts = ContactSet(
        emails=ranked_emails,
        phones=ranked_phones,
        best_email=ranked_emails[0].address if ranked_emails else None,
        best_phone=(ranked_phones[0].number or ranked_phones[0].raw) if ranked_phones else None,
        contact_page_url=contact_page_url,
        has_contact_form=has_contact_form,
    )
    if ranked_emails:
        status: ExtractionStatus = "extracted"
    elif ranked_phones or has_contact_form:
        status = "partial"
    else:
        status = "none"
    return base.model_copy(update={"status": status, "contacts": contacts, "fetches_used": fetches})


async def extract_for_geo(detection: DetectionResult, *, fetcher: PageFetcher) -> ExtractionResult:
    """Extract contacts for every detected page in one geo's detection result."""
    geo = detection.geo
    detected = [o for o in detection.outcomes if o.status == "detected" and o.detected is not None]
    _log.info("extract.start", geo=geo.url, detected_pages=len(detected))

    tiers_before = dict(fetcher.tier_counts)
    raw = await asyncio.gather(
        *(extract_candidate(o, fetcher=fetcher) for o in detected), return_exceptions=True
    )

    outcomes: list[ExtractionOutcome] = []
    for cand, result in zip(detected, raw, strict=True):
        if isinstance(result, BaseException):
            _log.error(
                "extract.candidate_failed",
                domain=cand.candidate.registrable_domain,
                error=str(result),
            )
            assert cand.detected is not None
            outcomes.append(
                ExtractionOutcome(
                    candidate=cand.candidate,
                    page_url=cand.detected.url,
                    page_confidence=cand.detected.confidence,
                    status="fetch_failed",
                )
            )
        else:
            outcomes.append(result)

    status_counts: dict[ExtractionStatus, int] = {}
    with_email = with_phone = form_only = 0
    fetches = 0
    for o in outcomes:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1
        fetches += o.fetches_used
        if o.contacts.emails:
            with_email += 1
        if o.contacts.phones:
            with_phone += 1
        if o.contacts.has_contact_form and not o.contacts.emails and not o.contacts.phones:
            form_only += 1

    fetch_tiers: dict[FetchTier, int] = {
        tier: fetcher.tier_counts[tier] - tiers_before.get(tier, 0) for tier in fetcher.tier_counts
    }
    _log.info(
        "extract.finish",
        geo=geo.url,
        status_counts=dict(status_counts),
        with_email=with_email,
        with_phone=with_phone,
        fetches_used=fetches,
    )
    return ExtractionResult(
        geo=geo,
        outcomes=outcomes,
        status_counts=status_counts,
        with_email=with_email,
        with_phone=with_phone,
        form_only=form_only,
        fetch_tiers=fetch_tiers,
        fetches_used=fetches,
    )
