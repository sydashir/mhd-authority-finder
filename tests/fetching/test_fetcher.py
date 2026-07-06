"""Two-tier fetch tests: httpx success, 403/SSL escalation, graceful degradation.

A fake in-process BrowserFetcher stands in for Playwright — no live Chromium
in unit tests.
"""

import ssl

import httpx
import pytest

from authority_finder.fetching import (
    FetchFailedError,
    NonHtmlError,
    PageFetcher,
)
from authority_finder.fetching.models import FetchForbiddenError

HTML = b"<html><head><title>Dept</title></head><body><h1>Behavioral Health</h1></body></html>"


def _html_response() -> httpx.Response:
    return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})


class FakeBrowser:
    """Records calls; returns canned HTML or raises to simulate a hard 403."""

    def __init__(self, *, forbidden: bool = False) -> None:
        self.calls: list[str] = []
        self._forbidden = forbidden

    async def fetch(self, url: str) -> tuple[bytes, str]:
        self.calls.append(url)
        if self._forbidden:
            raise FetchForbiddenError(f"403 from {url} (playwright)")
        return b"<html><title>Browser Rendered</title></html>", url

    async def aclose(self) -> None:
        return None


def _fetcher(handler: httpx.MockTransport, browser: FakeBrowser | None) -> PageFetcher:
    client = httpx.AsyncClient(transport=handler, follow_redirects=True)
    return PageFetcher(client=client, browser=browser)


async def test_httpx_success_never_touches_browser() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return _html_response()

    browser = FakeBrowser()
    fetcher = _fetcher(httpx.MockTransport(handler), browser)
    content = await fetcher.fetch("https://x.gov/page")

    assert content.fetch_tier == "httpx"
    assert content.title == "Dept"
    assert browser.calls == []
    assert fetcher.tier_counts == {"httpx": 1, "playwright": 0}


async def test_403_escalates_to_browser() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403)

    browser = FakeBrowser()
    fetcher = _fetcher(httpx.MockTransport(handler), browser)
    content = await fetcher.fetch("https://walled.gov/page")

    assert content.fetch_tier == "playwright"
    assert content.title == "Browser Rendered"
    assert browser.calls == ["https://walled.gov/page"]
    assert fetcher.tier_counts == {"httpx": 0, "playwright": 1}


async def test_ssl_failure_escalates_to_browser() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ConnectError("cert verify failed") from ssl.SSLCertVerificationError("bad")

    browser = FakeBrowser()
    fetcher = _fetcher(httpx.MockTransport(handler), browser)
    content = await fetcher.fetch("https://badcert.gov/page")

    assert content.fetch_tier == "playwright"
    assert browser.calls == ["https://badcert.gov/page"]


async def test_403_without_browser_degrades_to_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403)

    fetcher = _fetcher(httpx.MockTransport(handler), None)
    with pytest.raises(FetchFailedError):
        await fetcher.fetch("https://walled.gov/page")


async def test_hard_403_after_browser_degrades_to_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403)

    browser = FakeBrowser(forbidden=True)
    fetcher = _fetcher(httpx.MockTransport(handler), browser)
    with pytest.raises(FetchFailedError):
        await fetcher.fetch("https://walled.gov/page")
    assert browser.calls == ["https://walled.gov/page"]


async def test_transport_error_wrapped_as_fetch_failure() -> None:
    # Live S19 defect: a DNS/connect failure (httpx.TransportError) escaped fetch()
    # unwrapped, so the detector's `except FetchError` missed it and the candidate
    # crashed instead of falling back to the bounded crawl. It must not escalate to
    # the browser (a dead host won't render either).
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known")

    browser = FakeBrowser()
    fetcher = _fetcher(httpx.MockTransport(handler), browser)
    with pytest.raises(FetchFailedError):
        await fetcher.fetch("https://dead-domain.gov/page")
    assert browser.calls == []
    assert fetcher.fetch_count == 1


async def test_non_html_does_not_escalate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})

    browser = FakeBrowser()
    fetcher = _fetcher(httpx.MockTransport(handler), browser)
    with pytest.raises(NonHtmlError):
        await fetcher.fetch("https://x.gov/doc")
    assert browser.calls == []
