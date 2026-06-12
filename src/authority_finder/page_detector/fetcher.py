"""Async HTML page fetcher for candidate .gov/.edu sites.

Politeness is non-negotiable — these are government websites: robots.txt
respected per host, per-host concurrency capped at 2, a global cap of 8,
transient failures (5xx / timeouts — Session 4's Cloudflare 522 on
newportbeachca.gov is the canonical case) retried max 3 with backoff.
Responses stream against a 2 MB cap and only ``text/html`` is parsed.
"""

import asyncio
from http import HTTPStatus
from urllib.parse import urlparse

import httpx
import structlog
from lxml import html as lxml_html
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from authority_finder.robots import USER_AGENT, RobotsChecker

MAX_BYTES = 2_000_000
MAX_LINKS = 500
TEXT_SAMPLE_CHARS = 15_000
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class FetchError(RuntimeError):
    """Base class for page-fetch failures."""


class FetchFailedError(FetchError):
    """Network error or non-success status after retries."""


class _TransientError(FetchFailedError):
    """5xx — retried with backoff; surfaces as FetchFailedError when exhausted."""


class NonHtmlError(FetchError):
    """Response content-type is not text/html."""


class TooLargeError(FetchError):
    """Response body exceeded MAX_BYTES."""


class PageLink(BaseModel):
    """One internal/external anchor on a page."""

    text: str
    href: str


class PageContent(BaseModel):
    """Parsed page representation the scorer works from."""

    final_url: str
    title: str
    h1s: list[str]
    meta_description: str
    text_sample: str
    links: list[PageLink]
    has_mailto: bool
    has_tel: bool


class PageFetcher:
    """Polite fetch-and-parse for candidate pages. Counts fetches for budgeting."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        global_concurrency: int = 8,
        per_host_concurrency: int = 2,
    ) -> None:
        self._client = client
        self._robots = RobotsChecker(client=client, timeout=DEFAULT_TIMEOUT)
        self._global_sem = asyncio.Semaphore(global_concurrency)
        self._host_sems: dict[str, asyncio.Semaphore] = {}
        self._per_host = per_host_concurrency
        self.fetch_count = 0

    async def fetch(self, url: str) -> PageContent:
        """Fetch one page politely and parse it, or raise a typed :class:`FetchError`."""
        await self._robots.ensure_allowed(url)
        host = urlparse(url).netloc
        sem = self._host_sems.setdefault(host, asyncio.Semaphore(self._per_host))
        self.fetch_count += 1
        async with self._global_sem, sem:
            body, final_url = await self._get(url)
        return parse_html(body, final_url=final_url)

    async def _get(self, url: str) -> tuple[bytes, str]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=10.0),
            retry=retry_if_exception_type((httpx.TransportError, _TransientError)),
            reraise=True,
            before_sleep=_log_before_sleep,
        ):
            with attempt:
                async with self._client.stream(
                    "GET",
                    url,
                    headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                    timeout=DEFAULT_TIMEOUT,
                ) as resp:
                    if resp.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
                        raise _TransientError(f"{resp.status_code} from {url}")
                    if resp.status_code != HTTPStatus.OK:
                        raise FetchFailedError(f"{resp.status_code} from {url}")
                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type.lower():
                        raise NonHtmlError(f"content-type {content_type!r} at {url}")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise TooLargeError(f"body exceeds {MAX_BYTES} bytes at {url}")
                        chunks.append(chunk)
                    return b"".join(chunks), str(resp.url)
        raise RuntimeError("unreachable: AsyncRetrying yielded no attempts")


def parse_html(body: bytes, *, final_url: str) -> PageContent:
    """Parse raw HTML into the :class:`PageContent` the scorer consumes."""
    doc = lxml_html.fromstring(body or b"<html></html>")
    doc.make_links_absolute(final_url, resolve_base_href=True)

    title = (doc.findtext(".//title") or "").strip()
    h1s = [" ".join(h1.text_content().split()) for h1 in doc.findall(".//h1")][:5]
    meta_node = doc.find('.//meta[@name="description"]')
    meta_description = (meta_node.get("content") or "").strip() if meta_node is not None else ""

    for node in list(doc.iter("script", "style", "noscript")):
        node.drop_tree()
    text_sample = " ".join(doc.text_content().split())[:TEXT_SAMPLE_CHARS]

    links: list[PageLink] = []
    has_mailto = False
    has_tel = False
    for anchor in doc.findall(".//a[@href]"):
        href = (anchor.get("href") or "").strip()
        if href.startswith("mailto:"):
            has_mailto = True
            continue
        if href.startswith("tel:"):
            has_tel = True
            continue
        if not href or href.startswith(("javascript:", "#")):
            continue
        if len(links) < MAX_LINKS:
            links.append(PageLink(text=" ".join(anchor.text_content().split())[:200], href=href))

    return PageContent(
        final_url=final_url,
        title=title,
        h1s=[h for h in h1s if h],
        meta_description=meta_description,
        text_sample=text_sample,
        links=links,
        has_mailto=has_mailto,
        has_tel=has_tel,
    )


def _log_before_sleep(retry_state: RetryCallState) -> None:
    error = retry_state.outcome.exception() if retry_state.outcome is not None else None
    _log.warning(
        "page_fetch.retry",
        attempt=retry_state.attempt_number,
        error=str(error) if error else None,
    )
