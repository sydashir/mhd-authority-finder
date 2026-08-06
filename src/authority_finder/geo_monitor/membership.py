"""Which directories publish a given place — the ground truth behind Source Tag (ADR-037).

A prospect found for a geography that BOTH sites publish serves both, so its row must say so.
Built from the live sitemaps, which cost nothing: no search API, nothing billed.

Keyed on the PLACE, not the level, because the two sites classify the same place differently —
MHD publishes Palos Verdes as a city under Los Angeles County, AH publishes it at county level.
A level-sensitive key reads that as a miss and mislabels a both-sites place as MHD-only.
"""

from datetime import datetime

import httpx
import structlog

from authority_finder.discovery.models import GeoRef
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import SITES
from authority_finder.geo_monitor.url_parser import parse_geo_url

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

SiteMembership = dict[str, set[str]]


def place_key(*, state: str, county: str | None, city: str | None) -> str:
    """The most specific locality a geo page names: its state, plus that locality if any."""
    return f"{state}|{city or county or ''}"


def key_for(geo: GeoRef) -> str:
    return place_key(state=geo.state, county=geo.county, city=geo.city)


async def build_membership(*, client: httpx.AsyncClient, now: datetime) -> SiteMembership:
    """place key -> the site ids that publish it, across every configured directory."""
    fetcher = SitemapFetcher(client=client)
    membership: SiteMembership = {}
    for site_id, config in SITES.items():
        entries = await fetcher.fetch_all_geo_entries(config)
        for entry in entries:
            geo = parse_geo_url(entry.loc, config, now=now)
            if geo is None:
                continue
            membership.setdefault(
                place_key(state=geo.state, county=geo.county, city=geo.city), set()
            ).add(site_id)
    both = sum(1 for sites in membership.values() if len(sites) > 1)
    _log.info("membership.built", places=len(membership), served_by_both=both)
    return membership
