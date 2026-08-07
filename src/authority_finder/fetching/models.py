"""Shared fetch models and error hierarchy.

One :class:`PageContent` struct is produced by every fetch tier (httpx or
Playwright) so downstream consumers — the page detector's scorer and the
contact extractor — never care which tier served the bytes.
"""

from typing import Literal, Protocol

from pydantic import BaseModel

FetchTier = Literal["httpx", "playwright"]


class BrowserFetcher(Protocol):
    """A real-browser fetch tier. Returns ``(body_bytes, final_url)`` or raises a FetchError."""

    async def fetch(self, url: str) -> tuple[bytes, str]: ...

    async def aclose(self) -> None: ...


class FetchError(RuntimeError):
    """Base class for page-fetch failures."""


class FetchFailedError(FetchError):
    """Network error or non-success status after retries (and after escalation)."""


class FetchForbiddenError(FetchError):
    """HTTP 403 — escalatable to the Playwright tier; terminal if it recurs there."""


class SslError(FetchError):
    """TLS verification failure — escalatable to the Playwright tier."""


class NonHtmlError(FetchError):
    """Response content-type is not text/html."""


class TooLargeError(FetchError):
    """Response body exceeded the size cap."""


class PageLink(BaseModel):
    """One internal/external anchor on a page."""

    text: str
    href: str


class PageContent(BaseModel):
    """Parsed page representation shared by the scorer and contact extractor."""

    final_url: str
    title: str
    h1s: list[str]
    meta_description: str
    text_sample: str
    links: list[PageLink]
    has_mailto: bool
    has_tel: bool
    mailto_links: list[str] = []
    tel_links: list[str] = []
    has_web_form: bool = False
    fetch_tier: FetchTier = "httpx"
    # True when the anchor list hit MAX_LINKS and later anchors were dropped. Without this the
    # cap is an invisible recall ceiling: a page whose 501st link was the one we wanted looks
    # exactly like a page that never had it (ADR-039).
    links_truncated: bool = False
