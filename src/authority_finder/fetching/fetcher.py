"""Async HTML fetcher shared by the page detector and contact extractor.

Politeness is non-negotiable — these are government websites: robots.txt
respected per host, per-host concurrency capped at 2, a global cap of 8,
transient failures (5xx / timeouts — Session 4's Cloudflare 522 on
newportbeachca.gov is the canonical case) retried max 3 with backoff.
Responses stream against a 2 MB cap and only ``text/html`` is parsed.
"""

import asyncio
import ssl
from http import HTTPStatus
from urllib.parse import urlparse

import httpx
import structlog
from lxml import html as lxml_html
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from authority_finder.fetching.models import (
    BrowserFetcher,
    FetchFailedError,
    FetchForbiddenError,
    FetchTier,
    NonHtmlError,
    PageContent,
    PageLink,
    SslError,
    TooLargeError,
)
from authority_finder.robots import USER_AGENT, RobotsChecker

MAX_BYTES = 2_000_000
MAX_LINKS = 500
TEXT_SAMPLE_CHARS = 15_000
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class _TransientError(FetchFailedError):
    """5xx — retried with backoff; surfaces as FetchFailedError when exhausted."""


class PageFetcher:
    """Polite two-tier fetch-and-parse. httpx first; Playwright on 403 / SSL failure.

    Counts logical page fetches (one per :meth:`fetch` call regardless of tier)
    so the detector's crawl budget is tier-agnostic.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        browser: BrowserFetcher | None = None,
        global_concurrency: int = 8,
        per_host_concurrency: int = 2,
    ) -> None:
        self._client = client
        self._browser = browser
        self._robots = RobotsChecker(client=client, timeout=DEFAULT_TIMEOUT)
        self._global_sem = asyncio.Semaphore(global_concurrency)
        self._host_sems: dict[str, asyncio.Semaphore] = {}
        self._per_host = per_host_concurrency
        self.fetch_count = 0
        self.tier_counts: dict[FetchTier, int] = {"httpx": 0, "playwright": 0}

    async def fetch(self, url: str) -> PageContent:
        """Fetch one page politely and parse it, or raise a typed :class:`FetchError`."""
        await self._robots.ensure_allowed(url)
        host = urlparse(url).netloc
        sem = self._host_sems.setdefault(host, asyncio.Semaphore(self._per_host))
        self.fetch_count += 1
        async with self._global_sem, sem:
            body, final_url, tier = await self._fetch_with_escalation(url)
        self.tier_counts[tier] += 1
        return parse_html(body, final_url=final_url, fetch_tier=tier)

    async def _fetch_with_escalation(self, url: str) -> tuple[bytes, str, FetchTier]:
        """httpx tier, escalating to the browser tier on 403 / SSL failure."""
        try:
            body, final_url = await self._get(url)
            return body, final_url, "httpx"
        except (FetchForbiddenError, SslError) as exc:
            if self._browser is None:
                raise FetchFailedError(
                    f"{type(exc).__name__} and no browser fallback: {url}"
                ) from exc
            _log.info("fetch.escalate_playwright", url=url, reason=type(exc).__name__)
            try:
                body, final_url = await self._browser.fetch(url)
            except FetchForbiddenError as browser_exc:
                raise FetchFailedError(f"403 after playwright escalation: {url}") from browser_exc
            return body, final_url, "playwright"
        except httpx.TransportError as exc:
            # DNS / connect-timeout / read-timeout survived the retries. Wrap it as a
            # FetchError so the detector's crawl fallback treats it as a fetch failure
            # rather than an unhandled crash that aborts the whole candidate.
            raise FetchFailedError(f"transport error at {url}: {exc}") from exc

    async def _get(self, url: str) -> tuple[bytes, str]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=10.0),
            retry=retry_if_exception_type((httpx.TransportError, _TransientError)),
            reraise=True,
            before_sleep=_log_before_sleep,
        ):
            with attempt:
                try:
                    return await self._stream(url)
                except httpx.ConnectError as exc:
                    if _is_ssl_error(exc):
                        raise SslError(f"TLS failure at {url}: {exc}") from exc
                    raise
        raise RuntimeError("unreachable: AsyncRetrying yielded no attempts")

    async def _stream(self, url: str) -> tuple[bytes, str]:
        async with self._client.stream(
            "GET",
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=DEFAULT_TIMEOUT,
        ) as resp:
            if resp.status_code == HTTPStatus.FORBIDDEN:
                raise FetchForbiddenError(f"403 from {url}")
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


def parse_html(body: bytes, *, final_url: str, fetch_tier: FetchTier = "httpx") -> PageContent:
    """Parse raw HTML into the :class:`PageContent` consumers work from."""
    doc = lxml_html.fromstring(body or b"<html></html>")
    doc.make_links_absolute(final_url, resolve_base_href=True)

    title = (doc.findtext(".//title") or "").strip()
    h1s = [" ".join(h1.text_content().split()) for h1 in doc.findall(".//h1")][:5]
    meta_node = doc.find('.//meta[@name="description"]')
    meta_description = (meta_node.get("content") or "").strip() if meta_node is not None else ""

    has_web_form = any(_is_input_form(form) for form in doc.findall(".//form"))

    for node in list(doc.iter("script", "style", "noscript")):
        node.drop_tree()
    text_sample = " ".join(doc.text_content().split())[:TEXT_SAMPLE_CHARS]

    links: list[PageLink] = []
    links_truncated = False
    mailto: list[str] = []
    tel: list[str] = []
    for anchor in doc.findall(".//a[@href]"):
        href = (anchor.get("href") or "").strip()
        if href.lower().startswith("mailto:"):
            addr = href[len("mailto:") :].split("?", 1)[0]
            for part in addr.split(","):
                one = part.strip().lower()
                if one and one not in mailto:
                    mailto.append(one)
            continue
        if href.lower().startswith("tel:"):
            raw = href[len("tel:") :].strip()
            if raw and raw not in tel:
                tel.append(raw)
            continue
        if not href or href.startswith(("javascript:", "#")):
            continue
        if len(links) < MAX_LINKS:
            links.append(PageLink(text=" ".join(anchor.text_content().split())[:200], href=href))
        else:
            links_truncated = True

    return PageContent(
        final_url=final_url,
        title=title,
        h1s=[h for h in h1s if h],
        meta_description=meta_description,
        text_sample=text_sample,
        links=links,
        links_truncated=links_truncated,
        has_mailto=bool(mailto),
        has_tel=bool(tel),
        mailto_links=mailto,
        tel_links=tel,
        has_web_form=has_web_form,
        fetch_tier=fetch_tier,
    )


def _is_input_form(form: lxml_html.HtmlElement) -> bool:
    """A form that takes free-form human input (textarea or email/tel field) — an
    inquiry/contact form, not a bare search box."""
    if form.findall(".//textarea"):
        return True
    return any(
        (inp.get("type") or "").lower() in ("email", "tel") for inp in form.findall(".//input")
    )


def _is_ssl_error(exc: BaseException) -> bool:
    """True if a TLS verification error appears anywhere in the cause/context chain."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        current = current.__cause__ or current.__context__
    return False


def _log_before_sleep(retry_state: RetryCallState) -> None:
    error = retry_state.outcome.exception() if retry_state.outcome is not None else None
    _log.warning(
        "page_fetch.retry",
        attempt=retry_state.attempt_number,
        error=str(error) if error else None,
    )
