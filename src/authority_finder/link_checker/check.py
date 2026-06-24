"""Competitor outbound-link detection over a fetched page. Pure, no I/O.

Matching reuses the exact discipline of the federal/competitor exclusion logic
(:func:`registrable_domain` + :data:`COMPETITOR_DOMAINS`), so ``rehabs.com``
matches ``www.rehabs.com/florida`` and ``florida.rehabs.com`` but **not**
``rehabsomething.com``. A false competitor flag misleads outreach, so:
relative/scheme-relative hrefs are resolved against the page first, links to the
candidate's own registrable domain are skipped, and identical links are deduped.
"""

from urllib.parse import urljoin

from authority_finder.discovery.classify import registrable_domain
from authority_finder.domains import COMPETITOR_DOMAINS
from authority_finder.fetching.models import PageContent
from authority_finder.link_checker.models import CompetitorLink


def find_competitor_links(content: PageContent, *, candidate_domain: str) -> list[CompetitorLink]:
    """Outbound links from ``content`` to any of the 16 competitor domains."""
    found: dict[tuple[str, str], CompetitorLink] = {}
    for link in content.links:
        href = urljoin(content.final_url, link.href.strip())
        if not href.startswith(("http://", "https://")):
            continue
        domain = registrable_domain(href)
        if not domain or domain == candidate_domain or domain not in COMPETITOR_DOMAINS:
            continue
        key = (domain, href)
        if key not in found:
            found[key] = CompetitorLink(
                competitor_domain=domain,
                found_on_url=content.final_url,
                anchor_text=link.text.strip(),
                link_url=href,
            )
    return list(found.values())
