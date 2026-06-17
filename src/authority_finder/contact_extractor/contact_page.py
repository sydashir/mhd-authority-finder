"""Contact-page link discovery. Pure function, no I/O.

When a detected department page yields no email, the orchestrator follows one
or two same-registrable-domain links that look like contact / staff-directory
pages (directly addressing the Session 5 finding that .edu pages lean on
contact forms). This ranks those links; the orchestrator does the fetching.
"""

from urllib.parse import urlparse

from authority_finder.discovery.classify import registrable_domain
from authority_finder.fetching.models import PageContent
from authority_finder.page_detector.prefilter import junk_url_reason

# (keyword, weight) — matched against link text + URL path, lowercased.
CONTACT_KEYWORDS: tuple[tuple[str, float], ...] = (
    ("contact us", 3.0),
    ("contact-us", 3.0),
    ("staff directory", 3.0),
    ("department directory", 3.0),
    ("contact", 2.5),
    ("email us", 2.5),
    ("get in touch", 2.0),
    ("reach us", 2.0),
    ("directory", 1.5),
    ("staff", 1.0),
)


def find_contact_links(content: PageContent, *, domain: str, limit: int = 2) -> list[str]:
    """Same-domain links most likely to be a contact / directory page, ranked."""
    scored: list[tuple[float, str]] = []
    seen: set[str] = set()
    for link in content.links:
        href = link.href.split("#", 1)[0]
        if not href.startswith(("http://", "https://")) or href in seen:
            continue
        if registrable_domain(href) != domain or junk_url_reason(href) is not None:
            continue
        blob = f"{link.text} {urlparse(href).path}".lower()
        score = sum(weight for keyword, weight in CONTACT_KEYWORDS if keyword in blob)
        if score > 0:
            seen.add(href)
            scored.append((score, href))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [href for _, href in scored[:limit]]
