"""Sitemap watcher for MHD and AH.

Polls each site's sitemap index on demand, diffs against the persisted set of
previously seen URLs, and returns the newly-observed geo pages (state /
county / city) as structured :class:`GeoPage` records. Source of truth for
"which geos exist for outreach"; downstream pipeline steps consume the output
and never touch the sitemaps themselves.
"""

from authority_finder.geo_monitor.models import (
    GeoLevel,
    GeoPage,
    MonitorError,
    MonitorRun,
    SiteConfig,
    SitemapEntry,
    SiteState,
)
from authority_finder.geo_monitor.sites import SITES

__all__ = [
    "SITES",
    "GeoLevel",
    "GeoPage",
    "MonitorError",
    "MonitorRun",
    "SiteConfig",
    "SiteState",
    "SitemapEntry",
]
