"""Data models for the competitor backlink checker (component 6, ADR-011).

Precision-first (ADR-003/007/010): a wrong "links to competitor" flag misleads
outreach, so every match carries the page it was found on, the anchor text, and
the resolved href — a human can QA the flag without re-fetching.
"""

from pydantic import BaseModel

from authority_finder.discovery.models import CandidateSite


class CompetitorLink(BaseModel):
    """One outbound link from an authority page to a competitor domain."""

    competitor_domain: str  # the matched registrable domain, e.g. "recovery.com"
    found_on_url: str  # the page the link appears on (detected page or resources hop)
    anchor_text: str
    link_url: str  # the actual resolved (absolute) href


class LinkCheckResult(BaseModel):
    """Competitor-link findings for one candidate across the pages checked."""

    candidate: CandidateSite
    pages_checked: int = 0
    links_found: list[CompetitorLink] = []
    checked_ok: bool = True
    note: str = ""

    @property
    def competitor_domains(self) -> list[str]:
        """Unique competitor domains found, sorted — the deliverable's cell summary."""
        return sorted({link.competitor_domain for link in self.links_found})

    def found_on_pages(self, *, exclude: str = "") -> list[str]:
        """Pages the links were actually found on, excluding ``exclude``.

        The check covers the detected page AND one resources hop (ADR-011), so a link often
        lives on a sub-page. Showing only the contact URL made a correct detection look like
        a false positive to the client — the links were real, just on a page we never named.
        """
        seen = {link.found_on_url for link in self.links_found}
        seen.discard(exclude)
        return sorted(seen)
