"""Per-candidate detection: prefilter → fetch → score → bounded crawl fallback.

The crawl fallback activates when the surfaced URL was junk-rejected, failed
to fetch, or scored below the medium threshold: fetch the domain homepage,
rank its internal links by keyword affinity, follow the top
:data:`CRAWL_LINKS` same-domain links, and keep the best page seen anywhere.
Hard budget: :data:`MAX_FETCHES_PER_CANDIDATE` fetches per candidate
including the original attempt. The crawl never leaves the candidate's
registrable domain.

Wrong-state semantics: a wrong-state verdict on the surfaced page or the
homepage condemns the whole candidate (the domain is about the wrong place);
on a crawled subpage it only skips that page.
"""

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import structlog

from authority_finder.discovery.classify import registrable_domain
from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.page_detector.fetcher import FetchError, PageContent, PageFetcher
from authority_finder.page_detector.models import CandidateOutcome, DetectedPage
from authority_finder.page_detector.prefilter import junk_url_reason, prefilter_candidate
from authority_finder.page_detector.scorer import (
    MEDIUM_THRESHOLD,
    RESOURCE_MARKERS,
    TOPIC_KEYWORDS,
    WrongState,
    is_viable,
    score_page,
)
from authority_finder.robots import RobotsDisallowedError

MAX_FETCHES_PER_CANDIDATE = 6
CRAWL_LINKS = 4

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def rank_internal_links(content: PageContent, *, domain: str) -> list[str]:
    """Same-registrable-domain links ranked by keyword affinity of text + href."""
    scored: list[tuple[float, str]] = []
    seen: set[str] = set()
    for link in content.links:
        href = link.href.split("#", 1)[0]
        if not href.startswith(("http://", "https://")) or href in seen:
            continue
        if registrable_domain(href) != domain or junk_url_reason(href) is not None:
            continue
        blob = f"{link.text} {href}".lower()
        affinity = sum(2.0 for k in TOPIC_KEYWORDS if k in blob or k.replace(" ", "-") in blob)
        affinity += sum(1.0 for m in RESOURCE_MARKERS if m in blob or m.replace(" ", "-") in blob)
        if affinity > 0:
            seen.add(href)
            scored.append((affinity, href))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [href for _, href in scored]


def _better(current: DetectedPage | None, contender: DetectedPage) -> DetectedPage:
    if current is None or contender.score > current.score:
        return contender
    return current


_Attempt = Callable[[str], Awaitable[DetectedPage | WrongState | None]]


async def _crawl_for_better(
    best: DetectedPage | None,
    *,
    attempt: _Attempt,
    contents: dict[str, PageContent],
    homepage: str,
    original_url: str,
    domain: str,
) -> DetectedPage | WrongState | None:
    """Homepage + ranked-internal-links fallback. WrongState here means the homepage.

    ``attempt`` is idempotent per URL (the caller's tried-set returns ``None``
    on repeats), so calling it on an already-attempted homepage is a no-op.
    """
    home_scored = await attempt(homepage)
    if isinstance(home_scored, WrongState):
        return home_scored
    if home_scored is not None:
        best = _better(best, home_scored)
    crawl_source = contents.get(homepage) or contents.get(original_url)
    if crawl_source is not None:
        for href in rank_internal_links(crawl_source, domain=domain)[:CRAWL_LINKS]:
            sub_scored = await attempt(href)
            if sub_scored is None or isinstance(sub_scored, WrongState):
                continue
            best = _better(best, sub_scored)
    return best


async def process_candidate(
    candidate: CandidateSite, *, geo: GeoRef, fetcher: PageFetcher
) -> CandidateOutcome:
    """Run the full detection pipeline for one discovery candidate."""
    verdict = prefilter_candidate(candidate)
    if verdict.domain_rejection is not None:
        return CandidateOutcome(
            candidate=candidate, status="rejected", rejection_reason=verdict.domain_rejection
        )

    original_url = str(candidate.url)
    parsed = urlparse(original_url)
    homepage = f"{parsed.scheme}://{parsed.netloc}/"
    domain = registrable_domain(original_url)

    fetches = 0
    failures = 0
    tried: set[str] = set()
    contents: dict[str, PageContent] = {}

    async def attempt(url: str) -> DetectedPage | WrongState | None:
        nonlocal fetches, failures
        if url in tried or fetches >= MAX_FETCHES_PER_CANDIDATE:
            return None
        tried.add(url)
        fetches += 1
        try:
            content = await fetcher.fetch(url)
        except (FetchError, RobotsDisallowedError) as exc:
            failures += 1
            _log.debug("detect.fetch_failed", url=url, error=str(exc))
            return None
        contents[url] = content
        return score_page(content, geo=geo)

    best: DetectedPage | None = None
    if not verdict.url_is_junk:
        scored = await attempt(original_url)
        if isinstance(scored, WrongState):
            _log.info(
                "detect.wrong_state",
                candidate=candidate.registrable_domain,
                dominant=scored.dominant_state,
            )
            return CandidateOutcome(
                candidate=candidate,
                status="rejected",
                rejection_reason="wrong_state",
                fetches_used=fetches,
            )
        if scored is not None:
            best = scored

    if best is None or best.score < MEDIUM_THRESHOLD:
        fallback = await _crawl_for_better(
            best,
            attempt=attempt,
            contents=contents,
            homepage=homepage,
            original_url=original_url,
            domain=domain,
        )
        if isinstance(fallback, WrongState):
            return CandidateOutcome(
                candidate=candidate,
                status="rejected",
                rejection_reason="wrong_state",
                fetches_used=fetches,
            )
        if fallback is not None:
            best = fallback

    if best is not None and is_viable(best):
        return CandidateOutcome(
            candidate=candidate, status="detected", detected=best, fetches_used=fetches
        )
    if fetches > 0 and failures == fetches:
        return CandidateOutcome(candidate=candidate, status="fetch_failed", fetches_used=fetches)
    reason = "junk_url" if verdict.url_is_junk else "no_viable_page"
    return CandidateOutcome(
        candidate=candidate, status="rejected", rejection_reason=reason, fetches_used=fetches
    )
