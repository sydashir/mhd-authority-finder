"""Per-geo search-engine discovery.

Given a geo (state / county / city), issues targeted SerpAPI queries to
surface candidate ``.gov`` / ``.edu`` (and ``.us`` local-government) sites,
classifies and dedupes them by registrable domain, and returns structured
:class:`DiscoveryResult` records for downstream page detection. Does not
crawl candidate pages itself.
"""

from authority_finder.discovery.models import (
    CandidateSite,
    DiscoveryError,
    DiscoveryResult,
    DomainClass,
    GeoRef,
    SearchResult,
)

__all__ = [
    "CandidateSite",
    "DiscoveryError",
    "DiscoveryResult",
    "DomainClass",
    "GeoRef",
    "SearchResult",
]
