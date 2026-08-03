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
from authority_finder.page_detector.geography import ABBR_TO_SLUG

_ABBR_LEN = 2


def parse_geo_url(url: str, config: SiteConfig, *, now: datetime) -> GeoPage | None:
    """Parse one URL into a :class:`GeoPage`, or return ``None`` if it isn't a geo page."""
    parsed = urlparse(url)
    path = parsed.path

    # Try every shape and keep the first that yields a VALID state. Matching alone is not
    # enough: AH's primary pattern happily matches /support-groups/california/orange-county/
    # as state="support-groups", so stopping at the first regex hit would reject the page
    # before the topic patterns were ever tried.
    state = county = city = None
    for pattern in (config.geo_url_regex, *config.topic_url_regexes):
        match = pattern.match(path)
        if match is None:
            continue
        groups = match.groupdict()
        candidate = groups.get("state") or ""
        # Topic pages abbreviate the state (/ocd-treatment/tn/…) while /serving/ spells it
        # out; expand before the whitelist check or every topic page is rejected.
        if len(candidate) == _ABBR_LEN:
            candidate = ABBR_TO_SLUG.get(candidate.lower(), candidate)
        if candidate in US_STATE_SLUGS:
            state, county, city = candidate, groups.get("county"), groups.get("city")
            break

    if state is None:
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
