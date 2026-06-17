"""Orchestrator: status logic, contact-page fallback, budget, off-domain guard."""

import httpx

from authority_finder.contact_extractor.orchestrator import (
    MAX_CONTACT_FETCHES,
    extract_candidate,
    extract_for_geo,
)
from authority_finder.fetching import PageFetcher
from tests.contact_extractor.conftest import (
    candidate_outcome,
    detection_with,
    fetcher_for,
    html,
)


async def test_email_on_page_yields_extracted() -> None:
    url = "https://county.gov/behavioral-health"
    fetcher = fetcher_for({url: html(body="Reach us.", mailto="bh@county.gov", tel="916-555-1212")})
    outcome = await extract_candidate(candidate_outcome(url), fetcher=fetcher)

    assert outcome.status == "extracted"
    assert outcome.contacts.best_email == "bh@county.gov"
    assert outcome.contacts.best_phone == "+19165551212"
    assert outcome.fetches_used == 1


async def test_phone_only_is_partial() -> None:
    url = "https://county.gov/dept"
    fetcher = fetcher_for({url: html(body="Call us.", tel="916-555-1212")})
    outcome = await extract_candidate(candidate_outcome(url), fetcher=fetcher)
    assert outcome.status == "partial"
    assert outcome.contacts.best_email is None
    assert outcome.contacts.best_phone == "+19165551212"


async def test_contact_form_only_is_partial() -> None:
    url = "https://county.gov/dept"
    fetcher = fetcher_for({url: html(body="Use the form.", form=True)})
    outcome = await extract_candidate(candidate_outcome(url), fetcher=fetcher)
    assert outcome.status == "partial"
    assert outcome.contacts.has_contact_form
    assert not outcome.contacts.emails


async def test_nothing_found_is_none() -> None:
    url = "https://county.gov/dept"
    fetcher = fetcher_for({url: html(body="No contact info here at all.")})
    outcome = await extract_candidate(candidate_outcome(url), fetcher=fetcher)
    assert outcome.status == "none"


async def test_contact_page_fallback_when_no_email_on_page() -> None:
    url = "https://county.gov/dept"
    contact = "https://county.gov/contact-us"
    routes = {
        url: html(body="See contact page.", links=(("Contact Us", contact),)),
        contact: html(body="Dept inbox", mailto="health@county.gov"),
    }
    counter: list[str] = []
    fetcher = fetcher_for(routes, counter)
    outcome = await extract_candidate(candidate_outcome(url), fetcher=fetcher)

    assert outcome.status == "extracted"
    assert outcome.contacts.best_email == "health@county.gov"
    assert outcome.contacts.contact_page_url == contact
    assert outcome.contacts.emails[0].source == "contact_page"
    assert outcome.fetches_used == 2


async def test_contact_fetch_budget_capped() -> None:
    url = "https://county.gov/dept"
    links = tuple((f"Contact {i}", f"https://county.gov/contact-{i}") for i in range(5))
    routes = {url: html(body="links", links=links)}
    for i in range(5):
        routes[f"https://county.gov/contact-{i}"] = html(body="no email, just text")
    counter: list[str] = []
    fetcher = fetcher_for(routes, counter)
    outcome = await extract_candidate(candidate_outcome(url), fetcher=fetcher)
    # 1 page + at most MAX_CONTACT_FETCHES contact pages.
    assert outcome.fetches_used <= 1 + MAX_CONTACT_FETCHES
    assert len(counter) <= 1 + MAX_CONTACT_FETCHES


async def test_off_domain_contact_redirect_ignored() -> None:
    url = "https://county.gov/dept"
    contact = "https://county.gov/contact"

    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if u.endswith("/robots.txt"):
            return httpx.Response(404)
        if u == url:
            return httpx.Response(
                200,
                content=html(body="x", links=(("Contact Us", contact),)),
                headers={"content-type": "text/html"},
            )
        if u == contact:
            return httpx.Response(301, headers={"location": "https://vendor.com/leadform"})
        if "vendor.com" in u:
            return httpx.Response(
                200, content=html(mailto="sales@vendor.com"), headers={"content-type": "text/html"}
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    outcome = await extract_candidate(candidate_outcome(url), fetcher=PageFetcher(client=client))
    assert outcome.contacts.best_email != "sales@vendor.com"
    assert outcome.status in ("none", "partial")


async def test_fetch_failed_status() -> None:
    fetcher = fetcher_for({})
    outcome = await extract_candidate(candidate_outcome("https://dead.gov/dept"), fetcher=fetcher)
    assert outcome.status == "fetch_failed"


async def test_extract_for_geo_aggregates_coverage() -> None:
    good = "https://county.gov/bh"
    phone_only = "https://county.gov/clinic"
    nothing = "https://county.gov/empty"
    routes = {
        good: html(mailto="bh@county.gov"),
        phone_only: html(tel="916-555-1212"),
        nothing: html(body="nothing useful"),
    }
    fetcher = fetcher_for(routes)
    detection = detection_with([good, phone_only, nothing])
    result = await extract_for_geo(detection, fetcher=fetcher)

    assert result.with_email == 1
    assert result.with_phone == 1
    assert result.status_counts.get("extracted") == 1
    assert result.status_counts.get("partial") == 1
    assert result.status_counts.get("none") == 1
    assert result.fetch_tiers["httpx"] >= 3
