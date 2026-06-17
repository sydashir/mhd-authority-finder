"""Shared two-tier page fetcher: httpx first, Playwright fallback on 403/SSL.

Both the page detector and the contact extractor fetch through this module so
politeness rules, the 2 MB cap, robots handling, and the httpx→Playwright
escalation live in exactly one place.
"""

from authority_finder.fetching.fetcher import (
    DEFAULT_TIMEOUT,
    MAX_BYTES,
    PageFetcher,
    parse_html,
)
from authority_finder.fetching.models import (
    FetchError,
    FetchFailedError,
    FetchForbiddenError,
    FetchTier,
    NonHtmlError,
    PageContent,
    PageLink,
    SslError,
    TooLargeError,
)

__all__ = [
    "DEFAULT_TIMEOUT",
    "MAX_BYTES",
    "FetchError",
    "FetchFailedError",
    "FetchForbiddenError",
    "FetchTier",
    "NonHtmlError",
    "PageContent",
    "PageFetcher",
    "PageLink",
    "SslError",
    "TooLargeError",
    "parse_html",
]
