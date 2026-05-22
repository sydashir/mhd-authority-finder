"""Pure URL parser for geo pages.

No I/O. Takes a candidate URL plus a :class:`SiteConfig`, applies the site's
regex against the URL's path, validates the captured ``state`` slug against
:data:`US_STATE_SLUGS` (rejects ``/about``, ``/contact``, ``/blog`` and other
single-slug marketing paths on AH — see ADR-004), and returns a
:class:`GeoPage` whose ``url`` is normalized (scheme + host kept, trailing
slash added, query and fragment stripped).
"""

from datetime import datetime
from urllib.parse import urlparse

from authority_finder.geo_monitor.models import GeoLevel, GeoPage, SiteConfig
from authority_finder.geo_monitor.states import US_STATE_SLUGS


def parse_geo_url(url: str, config: SiteConfig, *, now: datetime) -> GeoPage | None:
    """Parse one URL into a :class:`GeoPage`, or return ``None`` if it isn't a geo page."""
    parsed = urlparse(url)
    path = parsed.path
    match = config.geo_url_regex.match(path)
    if match is None:
        return None

    state = match.group("state")
    county = match.group("county")
    city = match.group("city")

    if state not in US_STATE_SLUGS:
        return None

    level: GeoLevel = "city" if city else "county" if county else "state"

    if not path.endswith("/"):
        path = path + "/"
    if parsed.scheme and parsed.netloc:
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{path}"
    else:
        normalized_url = f"{config.base_url}{path}"

    return GeoPage(
        url=normalized_url,
        site_id=config.id,
        state=state,
        county=county,
        city=city,
        level=level,
        first_seen=now,
    )
