"""Competitor link checking over a candidate's detected page (+ one resources hop).

Mode (b) of ADR-011: check the detected page, then ONE same-domain
resources/links page if present. Budget ≤2 fetches total (shared httpx→Playwright
tier, so soft-blocked WAF pages still resolve). A caller that already holds the
detected page's :class:`PageContent` can pass it as ``content`` to skip the
re-fetch (then only the resources hop is new network). Per-candidate error
isolation: a failed detected-page fetch yields ``checked_ok=False``, never raises.
"""

import structlog

from authority_finder.discovery.classify import registrable_domain
from authority_finder.discovery.models import CandidateSite
from authority_finder.domains import COMPETITOR_DOMAINS
from authority_finder.fetching import FetchError, PageContent, PageFetcher
from authority_finder.link_checker.check import find_outbound_links
from authority_finder.link_checker.models import CompetitorLink, LinkCheckResult, OutboundLink
from authority_finder.link_checker.resources import find_resources_link
from authority_finder.robots import RobotsDisallowedError

MAX_LINK_CHECK_FETCHES = 2

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _safe_fetch(fetcher: PageFetcher, url: str) -> PageContent | None:
    try:
        return await fetcher.fetch(url)
    except (FetchError, RobotsDisallowedError) as exc:
        _log.debug("linkcheck.fetch_failed", url=url, error=str(exc))
        return None


async def check_links_for_candidate(
    candidate: CandidateSite,
    detected_page_url: str,
    *,
    fetcher: PageFetcher,
    content: PageContent | None = None,
) -> LinkCheckResult:
    """Competitor outbound links for one candidate's detected page (+ resources hop)."""
    domain = candidate.registrable_domain
    page = content if content is not None else await _safe_fetch(fetcher, detected_page_url)
    if page is None:
        return LinkCheckResult(
            candidate=candidate, checked_ok=False, note="detected page fetch failed"
        )

    outbound: list[OutboundLink] = find_outbound_links(page, candidate_domain=domain)
    truncated = page.links_truncated
    pages_checked = 1
    fetches = 0 if content is not None else 1

    for resources_url in find_resources_link(page, domain=domain, limit=1):
        if fetches >= MAX_LINK_CHECK_FETCHES:
            break
        hop = await _safe_fetch(fetcher, resources_url)
        fetches += 1
        if hop is None or registrable_domain(hop.final_url) != domain:
            continue
        pages_checked += 1
        outbound.extend(find_outbound_links(hop, candidate_domain=domain))
        truncated = truncated or hop.links_truncated

    deduped_out = {(link.domain, link.link_url): link for link in outbound}
    all_outbound = list(deduped_out.values())
    competitors: list[CompetitorLink] = [
        CompetitorLink(
            competitor_domain=link.domain,
            found_on_url=link.found_on_url,
            anchor_text=link.anchor_text,
            link_url=link.link_url,
        )
        for link in all_outbound
        if link.domain in COMPETITOR_DOMAINS
    ]
    if truncated:
        _log.warning("linkcheck.links_truncated", domain=domain, page=page.final_url)
    return LinkCheckResult(
        candidate=candidate,
        pages_checked=pages_checked,
        links_found=competitors,
        outbound_links=all_outbound,
        links_truncated=truncated,
        checked_ok=True,
    )
