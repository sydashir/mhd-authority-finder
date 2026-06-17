"""Playwright (headless Chromium) fetch tier — escalation target for 403 / SSL.

Launched once and reused for a whole run (Session 4 pattern). robots.txt is
enforced by :class:`PageFetcher` before this tier is ever called, so this class
just drives a genuine browser — and lets Chromium send its own real UA rather
than our bot string, which is the entire point of escalating (a WAF that 403s
our honest UA usually lets a real browser through). Used strictly as a
fallback; httpx serves the overwhelming majority of fetches.

Isolated in its own module so importing :mod:`authority_finder.fetching` never
pulls Playwright — only code that wires the fallback imports this.
"""

import asyncio
from http import HTTPStatus

import structlog
from playwright.async_api import Browser, Playwright, async_playwright

from authority_finder.fetching.fetcher import MAX_BYTES
from authority_finder.fetching.models import FetchFailedError, FetchForbiddenError

NAV_TIMEOUT_MS = 30_000

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PlaywrightBrowserFetcher:
    """Lazy-launched, reused headless Chromium. One browser instance per run."""

    def __init__(self, *, nav_timeout_ms: int = NAV_TIMEOUT_MS) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._nav_timeout_ms = nav_timeout_ms
        self._launch_lock = asyncio.Lock()

    async def _ensure_browser(self) -> Browser:
        # Double-checked under a lock: concurrent first-escalations must not each
        # launch (and orphan) a Chromium instance.
        if self._browser is None:
            async with self._launch_lock:
                if self._browser is None:
                    self._pw = await async_playwright().start()
                    self._browser = await self._pw.chromium.launch(headless=True)
                    _log.info("playwright.launched")
        return self._browser

    async def fetch(self, url: str) -> tuple[bytes, str]:
        browser = await self._ensure_browser()
        page = await browser.new_page()
        try:
            resp = await page.goto(url, timeout=self._nav_timeout_ms, wait_until="domcontentloaded")
            status = resp.status if resp is not None else 0
            if status == HTTPStatus.FORBIDDEN:
                raise FetchForbiddenError(f"403 from {url} (playwright)")
            if status >= HTTPStatus.BAD_REQUEST:
                raise FetchFailedError(f"{status} from {url} (playwright)")
            html = await page.content()
            final_url = page.url
        finally:
            await page.close()
        return html.encode("utf-8", "replace")[:MAX_BYTES], final_url

    async def aclose(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None
