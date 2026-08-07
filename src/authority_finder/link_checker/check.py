"""Outbound-link capture and competitor detection over a fetched page. Pure, no I/O.

Matching reuses the exact discipline of the federal/competitor exclusion logic
(:func:`registrable_domain` + :data:`COMPETITOR_DOMAINS`), so ``rehabs.com``
matches ``www.rehabs.com/florida`` and ``florida.rehabs.com`` but **not**
``rehabsomething.com``. A false competitor flag misleads outreach, so:
relative/scheme-relative hrefs are resolved against the page first, links to the
candidate's own registrable domain are skipped, and identical links are deduped.

**Capture is now unfiltered (ADR-039).** :func:`find_outbound_links` keeps every external
link; the competitor check is a filter applied afterwards. Filtering at capture is what made
the client's reported miss unanswerable without a full re-crawl — ``drugrehab.com`` is not one
of the brief's 16, so it was thrown away before anything was persisted.
"""

from collections import defaultdict
from urllib.parse import urljoin

from authority_finder.discovery.classify import registrable_domain
from authority_finder.domains import COMPETITOR_DOMAINS
from authority_finder.fetching.models import PageContent
from authority_finder.link_checker.classify import LinkClass, classify_domain
from authority_finder.link_checker.models import CompetitorLink, OutboundLink


def find_outbound_links(content: PageContent, *, candidate_domain: str) -> list[OutboundLink]:
    """Every external link leaving ``content``, deduped by (domain, resolved href).

    No allow-list. Whatever the page points at is kept, so widening the seed lists later is a
    pure re-classification rather than another crawl.
    """
    found: dict[tuple[str, str], OutboundLink] = {}
    for link in content.links:
        href = urljoin(content.final_url, link.href.strip())
        if not href.startswith(("http://", "https://")):
            continue
        domain = registrable_domain(href)
        if not domain or domain == candidate_domain:
            continue
        key = (domain, href)
        if key not in found:
            found[key] = OutboundLink(
                domain=domain,
                found_on_url=content.final_url,
                anchor_text=link.text.strip(),
                link_url=href,
            )
    return list(found.values())


def find_competitor_links(content: PageContent, *, candidate_domain: str) -> list[CompetitorLink]:
    """Outbound links from ``content`` to any of the 16 competitor domains.

    Deliberately still the 16 and nothing else: Competitor Links is a contractual column in a
    delivered sheet, so widening it would silently change what a shipped column means. The
    wider seed lists get their own columns instead.
    """
    return [
        CompetitorLink(
            competitor_domain=link.domain,
            found_on_url=link.found_on_url,
            anchor_text=link.anchor_text,
            link_url=link.link_url,
        )
        for link in find_outbound_links(content, candidate_domain=candidate_domain)
        if link.domain in COMPETITOR_DOMAINS
    ]


def classified_outbound_links(
    links: list[OutboundLink],
) -> dict[LinkClass, list[OutboundLink]]:
    """Group ``links`` by bucket, omitting the unknown ones.

    Unknown is dropped from the RESULT, not from the input: the raw links are what get
    persisted, so a domain that is unclassified today can be bucketed later without a re-crawl.
    """
    buckets: dict[LinkClass, list[OutboundLink]] = defaultdict(list)
    for link in links:
        bucket = classify_domain(link.domain)
        if bucket is not LinkClass.unknown:
            buckets[bucket].append(link)
    return dict(buckets)
