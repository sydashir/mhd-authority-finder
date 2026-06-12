"""Domain classification and per-geo dedup. Pure functions, no I/O.

tldextract runs fully offline — bundled PSL snapshot only (``suffix_list_urls=()``,
no disk cache) — so extraction is deterministic across environments and never
fetches the live public-suffix list at runtime.

The PSL has no entries under ``.gov``, so every state agency shares one
registrable domain (``dhcs.ca.gov`` → ``ca.gov``). Dedupe therefore uses a
*state-portal exception* (ADR-005): for registrable domains in
:data:`STATE_PORTAL_DOMAINS`, the label immediately under the portal is kept
(``www`` excluded), so distinct agencies stay distinct outreach rows.
``CandidateSite.registrable_domain`` holds this dedupe key — per-agency for
state portals, the true registrable domain everywhere else.
"""

from datetime import datetime

import tldextract

from authority_finder.discovery.models import (
    CandidateSite,
    DomainClass,
    GeoRef,
    SearchResult,
)
from authority_finder.geo_monitor.states import US_STATE_SLUGS

_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

_STATE_ABBREVIATIONS = frozenset(
    {
        "al",
        "ak",
        "az",
        "ar",
        "ca",
        "co",
        "ct",
        "de",
        "fl",
        "ga",
        "hi",
        "id",
        "il",
        "in",
        "ia",
        "ks",
        "ky",
        "la",
        "me",
        "md",
        "ma",
        "mi",
        "mn",
        "ms",
        "mo",
        "mt",
        "ne",
        "nv",
        "nh",
        "nj",
        "nm",
        "ny",
        "nc",
        "nd",
        "oh",
        "ok",
        "or",
        "pa",
        "ri",
        "sc",
        "sd",
        "tn",
        "tx",
        "ut",
        "vt",
        "va",
        "wa",
        "wv",
        "wi",
        "wy",
    }
)

# Best-effort: full-name portals (texas.gov), USPS-code portals (ny.gov), plus
# known irregulars. A miss degrades to registrable-domain dedupe for that
# state — coarser rows, never wrong ones.
STATE_PORTAL_DOMAINS = frozenset(
    {f"{slug.replace('-', '')}.gov" for slug in US_STATE_SLUGS}
    | {f"{abbr}.gov" for abbr in _STATE_ABBREVIATIONS}
    | {"mass.gov"}
)

KEPT_CLASSES: frozenset[DomainClass] = frozenset({"gov", "edu", "us_local"})


def classify_domain(url: str) -> DomainClass:
    """Bucket a URL by suffix: gov / edu / us_local (``.us``) / other."""
    suffix = _extract(url).suffix
    if suffix == "gov":
        return "gov"
    if suffix == "edu":
        return "edu"
    if suffix == "us" or suffix.endswith(".us"):
        return "us_local"
    return "other"


def registrable_domain(url: str) -> str:
    """True registrable domain per the public suffix list."""
    return _extract(url).top_domain_under_public_suffix


def dedupe_key(url: str) -> str:
    """Registrable domain, except state portals keep one extra label (non-www)."""
    ext = _extract(url)
    base = ext.top_domain_under_public_suffix
    if base in STATE_PORTAL_DOMAINS and ext.subdomain:
        labels = [label for label in ext.subdomain.split(".") if label != "www"]
        if labels:
            return f"{labels[-1]}.{base}"
    return base


def dedupe_candidates(
    results: list[SearchResult], *, geo: GeoRef, now: datetime
) -> tuple[list[CandidateSite], dict[DomainClass, int]]:
    """Collapse search results for one geo into ranked, deduplicated candidates.

    Returns ``(candidates, counts_by_class)``. Candidates cover gov / edu /
    us_local (us_local stays in, flagged by its class, pending real-world
    review); ``other`` is dropped from candidates but counted — Phase 2's
    authority filter gets sized from that evidence. Within a domain bucket the
    best-positioned result supplies url/title/snippet and source queries are
    merged in first-seen order. Output is sorted by best position.
    """
    buckets: dict[str, list[SearchResult]] = {}
    for result in results:
        buckets.setdefault(dedupe_key(str(result.link)), []).append(result)

    counts: dict[DomainClass, int] = {"gov": 0, "edu": 0, "us_local": 0, "other": 0}
    ranked: list[tuple[int, str, CandidateSite]] = []
    for key, group in buckets.items():
        best = min(group, key=lambda r: r.position)
        domain_class = classify_domain(str(best.link))
        counts[domain_class] += 1
        if domain_class not in KEPT_CLASSES:
            continue
        ranked.append(
            (
                best.position,
                key,
                CandidateSite(
                    registrable_domain=key,
                    url=best.link,
                    title=best.title,
                    snippet=best.snippet,
                    domain_class=domain_class,
                    geo=geo,
                    source_queries=list(dict.fromkeys(r.source_query for r in group)),
                    discovered_at=now,
                ),
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [candidate for _, _, candidate in ranked], counts
