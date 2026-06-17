"""Detector pipeline tests: crawl fallback, budgets, guards. MockTransport only."""

import httpx
import pytest

from authority_finder.fetching import (
    MAX_BYTES,
    NonHtmlError,
    PageFetcher,
    TooLargeError,
)
from authority_finder.page_detector.detector import MAX_FETCHES_PER_CANDIDATE, process_candidate
from tests.page_detector.conftest import (
    CALIFORNIA_GEO,
    ORANGE_COUNTY_GEO,
    html_page,
    make_candidate,
)

LONG_TEXT = "Public health programs for residents and families across the region. " * 15

GOOD_PAGE = html_page(
    title="Behavioral Health Services | Orange County",
    h1="Behavioral Health Services",
    body="Mental health and substance use treatment for Orange County, California. " + LONG_TEXT,
    mailto=True,
    tel=True,
)

NC_PAGE = html_page(
    title="Orange County Health Department",
    body="Serving Orange County, North Carolina. North Carolina services. "
    "More about North Carolina. " + LONG_TEXT,
)

THIN_HOMEPAGE = html_page(
    title="Example County",
    body="Welcome.",
    links=(
        ("Mental Health Services", "/services/mental-health"),
        ("Substance Abuse Treatment", "/services/substance-abuse"),
        ("Behavioral Health Resources", "/resources/behavioral-health"),
        ("Crisis Counseling", "/services/crisis"),
        ("Probation Department", "/departments/probation"),
        ("Parking", "/parking"),
        ("External", "https://elsewhere.org/mental-health"),
    ),
)


def fetcher_for(routes: dict[str, httpx.Response], counter: list[str]) -> PageFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        counter.append(url)
        if url in routes:
            return routes[url]
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    return PageFetcher(client=client)


def _html(body: bytes) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "text/html; charset=utf-8"})


async def test_good_page_detected_in_one_fetch() -> None:
    url = "https://ochealthinfo.gov/services/behavioral-health/"
    counter: list[str] = []
    fetcher = fetcher_for({url: _html(GOOD_PAGE)}, counter)
    outcome = await process_candidate(
        make_candidate(url, geo=ORANGE_COUNTY_GEO), geo=ORANGE_COUNTY_GEO, fetcher=fetcher
    )

    assert outcome.status == "detected"
    assert outcome.detected is not None and outcome.detected.confidence == "high"
    assert outcome.fetches_used == 1
    assert counter == [url]


async def test_competitor_rejected_without_any_fetch() -> None:
    counter: list[str] = []
    fetcher = fetcher_for({}, counter)
    outcome = await process_candidate(
        make_candidate("https://www.samhsa.gov/find-help/"), geo=CALIFORNIA_GEO, fetcher=fetcher
    )
    assert outcome.status == "rejected"
    assert outcome.rejection_reason == "competitor"
    assert counter == []


async def test_wrong_state_page_rejects_candidate() -> None:
    url = "https://orangecountync.gov/health/"
    counter: list[str] = []
    fetcher = fetcher_for({url: _html(NC_PAGE)}, counter)
    outcome = await process_candidate(
        make_candidate(url, geo=ORANGE_COUNTY_GEO), geo=ORANGE_COUNTY_GEO, fetcher=fetcher
    )
    assert outcome.status == "rejected"
    assert outcome.rejection_reason == "wrong_state"


async def test_pdf_candidate_survives_via_homepage_crawl() -> None:
    pdf = "https://example.gov/files/report.pdf"
    home = "https://example.gov/"
    good = "https://example.gov/services/mental-health"
    counter: list[str] = []
    fetcher = fetcher_for(
        {
            home: _html(THIN_HOMEPAGE),
            good: _html(GOOD_PAGE),
            "https://example.gov/services/substance-abuse": _html(THIN_HOMEPAGE),
            "https://example.gov/resources/behavioral-health": _html(THIN_HOMEPAGE),
            "https://example.gov/services/crisis": _html(THIN_HOMEPAGE),
        },
        counter,
    )
    outcome = await process_candidate(
        make_candidate(pdf, geo=ORANGE_COUNTY_GEO), geo=ORANGE_COUNTY_GEO, fetcher=fetcher
    )
    assert outcome.status == "detected"
    assert outcome.detected is not None
    assert outcome.detected.url == good
    assert pdf not in counter
    assert outcome.fetches_used <= MAX_FETCHES_PER_CANDIDATE


async def test_crawl_budget_enforced() -> None:
    # Topical link TEXT (ranks high) but neutral hrefs to thin pages: every
    # stage runs, nothing viable, and the 6-fetch ceiling is hit exactly.
    home = "https://example.gov/"
    homepage = html_page(
        title="Example County",
        body="Welcome.",
        links=tuple((f"Mental Health Counseling {i}", f"/d{i}") for i in range(6)),
    )
    thin = _html(html_page(title="Thin", body="x"))
    routes = {home: _html(homepage)}
    for i in range(6):
        routes[f"https://example.gov/d{i}"] = thin
    counter: list[str] = []
    fetcher = fetcher_for(routes, counter)
    outcome = await process_candidate(
        make_candidate("https://example.gov/landing"), geo=CALIFORNIA_GEO, fetcher=fetcher
    )
    assert outcome.fetches_used == MAX_FETCHES_PER_CANDIDATE
    assert len(counter) == MAX_FETCHES_PER_CANDIDATE
    assert outcome.status == "rejected"
    assert outcome.rejection_reason == "no_viable_page"


async def test_crawl_never_leaves_registrable_domain() -> None:
    home = "https://example.gov/"
    counter: list[str] = []
    fetcher = fetcher_for({home: _html(THIN_HOMEPAGE)}, counter)
    await process_candidate(
        make_candidate("https://example.gov/files/report.pdf"), geo=CALIFORNIA_GEO, fetcher=fetcher
    )
    assert all("elsewhere.org" not in url for url in counter)


async def test_all_fetches_failed() -> None:
    counter: list[str] = []
    fetcher = fetcher_for({}, counter)
    outcome = await process_candidate(
        make_candidate("https://dead.gov/page"), geo=CALIFORNIA_GEO, fetcher=fetcher
    )
    assert outcome.status == "fetch_failed"


async def test_robots_disallow_blocks_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        return _html(GOOD_PAGE)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    fetcher = PageFetcher(client=client)
    outcome = await process_candidate(
        make_candidate("https://blocked.gov/page"), geo=CALIFORNIA_GEO, fetcher=fetcher
    )
    assert outcome.status == "fetch_failed"


async def test_content_type_guard() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/robots.txt"):
            return httpx.Response(404)
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    fetcher = PageFetcher(client=client)
    with pytest.raises(NonHtmlError):
        await fetcher.fetch("https://example.gov/image-page")


async def test_size_cap_guard() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/robots.txt"):
            return httpx.Response(404)
        return httpx.Response(
            200,
            content=b"x" * (MAX_BYTES + 1),
            headers={"content-type": "text/html"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    fetcher = PageFetcher(client=client)
    with pytest.raises(TooLargeError):
        await fetcher.fetch("https://example.gov/huge")


async def test_transient_5xx_retried_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if str(request.url).endswith("/robots.txt"):
            return httpx.Response(404)
        calls += 1
        if calls == 1:
            return httpx.Response(522)
        return _html(GOOD_PAGE)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    fetcher = PageFetcher(client=client)
    content = await fetcher.fetch("https://flaky.gov/page")
    assert calls == 2
    assert "Behavioral Health" in content.title


async def test_offdomain_redirect_never_scored() -> None:
    gov_url = "https://greenfieldca.gov/408/Addiction-Treatment"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if url == gov_url:
            return httpx.Response(301, headers={"location": "https://palmerlakerecovery.com/"})
        if "palmerlakerecovery.com" in url:
            return _html(GOOD_PAGE)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    fetcher = PageFetcher(client=client)
    outcome = await process_candidate(
        make_candidate(gov_url, geo=CALIFORNIA_GEO), geo=CALIFORNIA_GEO, fetcher=fetcher
    )
    assert outcome.status != "detected"
    assert outcome.detected is None
