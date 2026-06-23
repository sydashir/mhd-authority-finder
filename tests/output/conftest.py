"""Builders for output tests."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.contact_extractor.models import (
    ContactSet,
    EmailHit,
    ExtractionOutcome,
    PhoneHit,
)
from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.page_detector.models import Confidence


def geo_ref(level: str = "county", *, site_id: str = "mhd") -> GeoRef:
    return GeoRef(
        site_id=site_id,
        url="https://inpatientmentalhealthfinder.com/serving/california/orange-county/",
        level=level,  # type: ignore[arg-type]
        state="california",
        county="orange-county" if level in ("county", "city") else None,
        city="newport-beach" if level == "city" else None,
    )


def outcome(
    *,
    domain: str = "ochealthinfo.gov",
    page_url: str = "https://ochealthinfo.gov/behavioral-health",
    email: str | None = "bh@ochealthinfo.gov",
    phone: str | None = "+17148341234",
    confidence: Confidence = "high",
    snippet: str = "Orange County behavioral health services and crisis support.",
    geo: GeoRef | None = None,
) -> ExtractionOutcome:
    emails = [EmailHit(address=email, source="mailto", confidence=0.9)] if email else []
    phones = [PhoneHit(number=phone, raw=phone or "", source="tel")] if phone else []
    contacts = ContactSet(
        emails=emails,
        phones=phones,
        best_email=email,
        best_phone=phone,
    )
    candidate = CandidateSite(
        registrable_domain=domain,
        url=HttpUrl(page_url),
        title="Behavioral Health | Orange County",
        snippet=snippet,
        domain_class="gov",
        geo=geo or geo_ref(),
        source_queries=["q1"],
        discovered_at=datetime.now(UTC),
    )
    return ExtractionOutcome(
        candidate=candidate,
        page_url=page_url,
        page_confidence=confidence,
        status="extracted" if email else "partial",
        contacts=contacts,
    )
