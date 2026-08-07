"""Data models for the competitor backlink checker (component 6, ADR-011).

Precision-first (ADR-003/007/010): a wrong "links to competitor" flag misleads
outreach, so every match carries the page it was found on, the anchor text, and
the resolved href — a human can QA the flag without re-fetching.
"""

from pydantic import BaseModel

from authority_finder.discovery.models import CandidateSite
from authority_finder.link_checker.classify import LinkClass, classify_domain


class OutboundLink(BaseModel):
    """One external link leaving an authority page, whatever it points at.

    Captured BEFORE any filtering (ADR-039). The old code discarded everything outside the
    brief's 16 at capture time, so a later question — "does this page link to drugrehab.com?" —
    could only be answered by re-crawling every page. Keeping the raw link means the seed lists
    can widen without touching the network again.
    """

    domain: str  # registrable domain, e.g. "drugrehab.com"
    found_on_url: str  # the page the link appears on (detected page or resources hop)
    anchor_text: str
    link_url: str  # the actual resolved (absolute) href


class CompetitorLink(BaseModel):
    """One outbound link from an authority page to a competitor domain."""

    competitor_domain: str  # the matched registrable domain, e.g. "recovery.com"
    found_on_url: str  # the page the link appears on (detected page or resources hop)
    anchor_text: str
    link_url: str  # the actual resolved (absolute) href


class LinkCheckResult(BaseModel):
    """Outbound-link findings for one candidate across the pages checked.

    ``links_found`` stays the brief's 16 and feeds the contractual Competitor Links column.
    ``outbound_links`` is everything the pages pointed at; the three newer columns are derived
    views over it, so widening a seed list never requires another crawl (ADR-039).
    """

    candidate: CandidateSite
    pages_checked: int = 0
    links_found: list[CompetitorLink] = []
    outbound_links: list[OutboundLink] = []
    checked_ok: bool = True
    # Set when any checked page hit MAX_LINKS, i.e. this candidate's link list is incomplete.
    links_truncated: bool = False
    note: str = ""

    @property
    def competitor_domains(self) -> list[str]:
        """Unique competitor domains found, sorted — the deliverable's cell summary."""
        return sorted({link.competitor_domain for link in self.links_found})

    def _bucket(self, bucket: LinkClass) -> list[OutboundLink]:
        return [link for link in self.outbound_links if classify_domain(link.domain) is bucket]

    def _domains(self, bucket: LinkClass) -> list[str]:
        return sorted({link.domain for link in self._bucket(bucket)})

    @property
    def addiction_directories(self) -> list[str]:
        """Addiction directories linked from the checked pages — the 16 plus verified seeds."""
        return self._domains(LinkClass.addiction_directory)

    @property
    def mental_health_directories(self) -> list[str]:
        return self._domains(LinkClass.mental_health_directory)

    @property
    def support_groups(self) -> list[str]:
        return self._domains(LinkClass.support_group)

    @property
    def support_groups_found_on(self) -> list[str]:
        """Pages the support-group links actually appear on.

        Named separately from the domains for the same reason ``found_on_pages`` exists: a
        correct finding on a sub-page reads as a false positive when the sheet only ever
        names the contact URL.
        """
        return sorted({link.found_on_url for link in self._bucket(LinkClass.support_group)})

    def found_on_pages(self, *, exclude: str = "") -> list[str]:
        """Pages the links were actually found on, excluding ``exclude``.

        The check covers the detected page AND one resources hop (ADR-011), so a link often
        lives on a sub-page. Showing only the contact URL made a correct detection look like
        a false positive to the client — the links were real, just on a page we never named.
        """
        seen = {link.found_on_url for link in self.links_found}
        seen.discard(exclude)
        return sorted(seen)
