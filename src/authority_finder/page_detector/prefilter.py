"""Pre-fetch candidate filtering. Pure functions, zero I/O.

Domain-level rejections (competitor, federal) kill a candidate before any
HTTP traffic. URL-level junk (non-HTML files, news/blog paths, search
results, login pages) rejects only the *surfaced URL* — the candidate
survives into the crawl fallback, because a good domain that surfaced via a
PDF still deserves its homepage crawled.
"""

from typing import Literal, NamedTuple
from urllib.parse import parse_qs, urlparse

from authority_finder.discovery.models import CandidateSite
from authority_finder.domains import is_competitor, is_federal

NON_HTML_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".mp3",
    ".mp4",
    ".xml",
    ".kml",
)
JUNK_PATH_SEGMENTS = (
    "/news/",
    "/press/",
    "/press-releases/",
    "/pressroom/",
    "/blog/",
    "/blogs/",
    "/events/",
    "/calendar/",
    "/search/",
)
JUNK_PATH_SUFFIXES = ("/news", "/press", "/blog", "/events", "/search")
LOGIN_MARKERS = ("login", "signin", "sign-in", "logon")
SEARCH_QUERY_KEYS = frozenset({"q", "s", "search", "searchtext", "query", "keywords"})

DomainRejection = Literal["competitor", "federal"]


class PrefilterVerdict(NamedTuple):
    """Pre-fetch verdict: domain-dead, junk-surfaced-URL, or clean."""

    domain_rejection: DomainRejection | None
    url_is_junk: bool
    junk_detail: str | None


def junk_url_reason(url: str) -> str | None:
    """Why this URL shouldn't be fetched as a candidate page, or ``None`` if fine."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(NON_HTML_EXTENSIONS):
        return f"non-html extension ({path.rsplit('.', 1)[-1]})"
    if any(segment in path for segment in JUNK_PATH_SEGMENTS):
        return "news/blog/events/search path"
    if path.rstrip("/").endswith(JUNK_PATH_SUFFIXES):
        return "news/blog/events/search path"
    if any(marker in path for marker in LOGIN_MARKERS):
        return "login page"
    query_keys = {key.lower() for key in parse_qs(parsed.query)}
    if query_keys & SEARCH_QUERY_KEYS:
        return "search-results query string"
    return None


def prefilter_candidate(candidate: CandidateSite) -> PrefilterVerdict:
    """Apply all pre-fetch checks to one discovery candidate."""
    url = str(candidate.url)
    if is_competitor(url):
        return PrefilterVerdict("competitor", url_is_junk=False, junk_detail=None)
    if is_federal(url):
        return PrefilterVerdict("federal", url_is_junk=False, junk_detail=None)
    reason = junk_url_reason(url)
    return PrefilterVerdict(None, url_is_junk=reason is not None, junk_detail=reason)
