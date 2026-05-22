"""Static :class:`SiteConfig` instances for the two monitored sites.

Source of truth: ``docs/sites.md``. Both sites run WordPress + Rank Math so
the sitemap shape is identical; the regexes differ because AH has no URL
prefix while MHD has ``/serving/``.
"""

import re

from authority_finder.geo_monitor.models import SiteConfig

_SLUG = r"[a-z0-9-]+"

MHD = SiteConfig(
    id="mhd",
    name="Inpatient Mental Health Finder",
    base_url="https://inpatientmentalhealthfinder.com",
    sitemap_index_url="https://inpatientmentalhealthfinder.com/sitemap_index.xml",
    geo_url_regex=re.compile(
        rf"^/serving/(?P<state>{_SLUG})(/(?P<county>{_SLUG}))?(/(?P<city>{_SLUG}))?/?$"
    ),
    slug_field_order=("state", "county", "city"),
)

AH = SiteConfig(
    id="ah",
    name="Addiction Hotline",
    base_url="https://addictionhotline.com",
    sitemap_index_url="https://addictionhotline.com/sitemap_index.xml",
    geo_url_regex=re.compile(
        rf"^/(?P<state>{_SLUG})(/(?P<county>{_SLUG}))?(/(?P<city>{_SLUG}))?/?$"
    ),
    slug_field_order=("state", "county", "city"),
)

SITES: dict[str, SiteConfig] = {MHD.id: MHD, AH.id: AH}
