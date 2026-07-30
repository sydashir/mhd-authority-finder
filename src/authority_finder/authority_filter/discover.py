"""Discover non-.gov/.edu authority organizations for a geo (brief component 3).

Returns plain :class:`CandidateSite` objects carrying ``domain_class="other"`` — the bucket
ADR-006 instrumented, counted, and always saw as zero because ``site:.gov OR site:.edu``
structurally cannot return an organization like ncala.org. These are that bucket, rescued.

Emitting the same type discovery emits is the whole design. The pipeline merges them into
``DiscoveryResult.candidates`` BEFORE detection, so authority candidates run the identical
downstream path — wrong-state validation (ADR-020/024), junk-page detection, the hotline
blocklist, contact-trust banding, competitor and federal exclusion. Gate-reuse is therefore
structural rather than a promise: there is no separate code path that could skip a gate.

Domain Rating is attached as a SIGNAL, never a gate. The competitor-backlink study
(`docs/competitor-backlink-analysis.md`) found the median organization that demonstrably
links to a working directory scores DR 20, so the brief's "e.g. DR 40+" would discard 92% of
exactly the organizations we want. Selection is done by type (platform blocklist) and by the
geo gates downstream; DR rides along for the outreach rep to see.
"""

from datetime import datetime

import structlog

from authority_finder.authority_filter.ahrefs_client import AhrefsClient, DomainRating
from authority_finder.authority_filter.filter import registrable, select_scoreable
from authority_finder.authority_filter.queries import build_authority_queries
from authority_finder.discovery.models import CandidateSite, GeoRef, SearchResult
from authority_finder.discovery.serpapi_client import SerpApiClient
from authority_finder.geo_monitor.models import GeoPage

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def authority_candidates_for_geo(
    geo: GeoPage,
    *,
    serp_client: SerpApiClient,
    ahrefs_client: AhrefsClient | None,
    now: datetime,
) -> tuple[list[CandidateSite], dict[str, DomainRating]]:
    """Unrestricted search for one geo, type-filtered, with DR attached as a signal.

    ``ahrefs_client`` may be None (no key configured) — discovery still works, the rows
    simply carry no DR. The feature degrades rather than failing the run.
    """
    ref = GeoRef.from_geo_page(geo)
    best: dict[str, SearchResult] = {}
    queries_by_domain: dict[str, list[str]] = {}

    for query in build_authority_queries(geo):
        try:
            raw = await serp_client.search(query)
        except Exception as exc:  # one bad query must not lose the geo
            _log.warning("authority.query_failed", query=query, error=str(exc))
            continue
        for position, entry in enumerate(raw.data.get("organic_results") or [], start=1):
            link = entry.get("link")
            if not link:
                continue
            result = SearchResult(
                position=position,
                link=link,
                title=entry.get("title") or "",
                snippet=entry.get("snippet") or "",
                source_query=query,
            )
            host = str(result.link)
            best.setdefault(host, result)
            queries_by_domain.setdefault(host, []).append(query)

    selection = select_scoreable(list(best))
    _log.info(
        "authority.selected",
        geo=geo.url,
        scoreable=len(selection.scoreable),
        platform_blocked=len(selection.skipped_platform),
        competitor=len(selection.skipped_competitor),
        gov_edu=len(selection.skipped_domain_class),
    )

    ratings: dict[str, DomainRating] = {}
    if ahrefs_client is not None and selection.scoreable:
        ratings = await ahrefs_client.domain_ratings(selection.scoreable)

    # Map each surviving registrable domain back to the best URL that produced it.
    by_root: dict[str, SearchResult] = {}
    for host, result in best.items():
        by_root.setdefault(registrable(host), result)

    candidates: list[CandidateSite] = []
    for root in selection.scoreable:
        result = by_root.get(root)
        if result is None:
            continue
        candidates.append(
            CandidateSite(
                registrable_domain=root,
                url=result.link,
                title=result.title,
                snippet=result.snippet,
                domain_class="other",
                geo=ref,
                source_queries=list(dict.fromkeys(queries_by_domain.get(str(result.link), []))),
                discovered_at=now,
            )
        )
    return candidates, ratings
