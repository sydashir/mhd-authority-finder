"""Shared builders for contact_extractor tests. No network."""

from datetime import UTC, datetime

import httpx
from pydantic import HttpUrl

from authority_finder.contact_extractor.models import ContactSet
from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.fetching import PageContent, PageFetcher
from authority_finder.page_detector.models import (
    CandidateOutcome,
    Confidence,
    DetectedPage,
    DetectionResult,
)

ORANGE_COUNTY = GeoRef(
    site_id="mhd",
    url="https://inpatientmentalhealthfinder.com/serving/california/orange-county/",
    level="county",
    state="california",
    county="orange-county",
)


def page(
    *,
    final_url: str = "https://county.gov/dept",
    text: str = "",
    mailto: list[str] | None = None,
    tel: list[str] | None = None,
    links: list[tuple[str, str]] | None = None,
    has_web_form: bool = False,
) -> PageContent:
    return PageContent(
        final_url=final_url,
        title="",
        h1s=[],
        meta_description="",
        text_sample=text,
        links=[{"text": t, "href": h} for t, h in (links or [])],  # type: ignore[list-item]
        has_mailto=bool(mailto),
        has_tel=bool(tel),
        mailto_links=mailto or [],
        tel_links=tel or [],
        has_web_form=has_web_form,
    )


def candidate_outcome(url: str, *, confidence: Confidence = "high") -> CandidateOutcome:
    cand = CandidateSite(
        registrable_domain="county.gov",
        url=HttpUrl(url),
        title="Behavioral Health",
        snippet="",
        domain_class="gov",
        geo=ORANGE_COUNTY,
        source_queries=["q1"],
        discovered_at=datetime.now(UTC),
    )
    detected = DetectedPage(
        url=url, score=10.0, confidence=confidence, signals=[], state_validated=True
    )
    return CandidateOutcome(candidate=cand, status="detected", detected=detected)


def detection_with(urls: list[str]) -> DetectionResult:
    outcomes = [candidate_outcome(u) for u in urls]
    return DetectionResult(
        geo=ORANGE_COUNTY,
        outcomes=outcomes,
        status_counts={"detected": len(outcomes)},
    )


def html(
    *,
    body: str = "",
    mailto: str | None = None,
    tel: str | None = None,
    links: tuple[tuple[str, str], ...] = (),
    form: bool = False,
) -> bytes:
    parts = [f"<p>{body}</p>"]
    if mailto:
        parts.append(f'<a href="mailto:{mailto}">Email</a>')
    if tel:
        parts.append(f'<a href="tel:{tel}">Call</a>')
    parts.extend(f'<a href="{href}">{text}</a>' for text, href in links)
    if form:
        parts.append('<form><textarea name="message"></textarea></form>')
    return f"<html><body>{''.join(parts)}</body></html>".encode()


def fetcher_for(routes: dict[str, bytes], counter: list[str] | None = None) -> PageFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if counter is not None:
            counter.append(url)
        if url in routes:
            return httpx.Response(200, content=routes[url], headers={"content-type": "text/html"})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    return PageFetcher(client=client)


def best_emails(contacts: ContactSet) -> list[str]:
    return [e.address for e in contacts.emails]
