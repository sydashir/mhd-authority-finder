"""Resources/links-page discovery for the competitor link check. Pure, no I/O.

Directories of external orgs (and the competitor links we hunt for) usually sit on
a "resources / links / community partners / helpful links" page, not the detected
department page. This ranks same-domain internal links most likely to be that page;
the orchestrator fetches the top one (ADR-011, mode (b)). Same single-best-match
weighting + junk/own-domain discipline as the contact-page picker.
"""

from urllib.parse import urlparse

from authority_finder.discovery.classify import registrable_domain
from authority_finder.fetching.models import PageContent
from authority_finder.page_detector.prefilter import junk_url_reason

RESOURCE_KEYWORDS: tuple[tuple[str, float], ...] = (
    ("community partners", 4.0),
    ("community resources", 4.0),
    ("helpful links", 4.0),
    ("resources and links", 4.0),
    ("related links", 3.5),
    ("external links", 3.5),
    ("useful links", 3.5),
    ("partners", 3.0),
    ("resources", 3.0),
    ("links", 2.0),
)


def find_resources_link(content: PageContent, *, domain: str, limit: int = 1) -> list[str]:
    """Same-domain internal links most likely to be a resources/links page, ranked."""
    scored: list[tuple[float, str]] = []
    seen: set[str] = set()
    for link in content.links:
        href = link.href.split("#", 1)[0]
        if not href.startswith(("http://", "https://")) or href in seen:
            continue
        if registrable_domain(href) != domain or junk_url_reason(href) is not None:
            continue
        blob = f"{link.text} {urlparse(href).path}".lower()
        score = max(
            (weight for keyword, weight in RESOURCE_KEYWORDS if keyword in blob), default=0.0
        )
        if score > 0:
            seen.add(href)
            scored.append((score, href))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [href for _, href in scored[:limit]]
