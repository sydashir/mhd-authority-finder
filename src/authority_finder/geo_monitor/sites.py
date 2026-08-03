"""Static :class:`SiteConfig` instances for the two monitored sites.

Source of truth: ``docs/sites.md``. Both sites run WordPress + Rank Math so
the sitemap shape is identical; the regexes differ because AH has no URL
prefix while MHD has ``/serving/``.
"""

import re

from authority_finder.geo_monitor.models import SiteConfig

_SLUG = r"[a-z0-9-]+"
_ABBR = r"[a-z]{2}"

# Content-type prefixes observed in the live sitemaps. Listing them explicitly (rather than
# accepting any first segment) is what keeps /review-us/ryan-h/ from parsing as a state.
_AH_TOPICS = "support-groups|drug-rehab-centers"
_MHD_TOPICS = (
    "outpatient-treatment|inpatient-treatment|schizophrenia-treatment|ptsd-treatment"
    "|depression-treatment|group-addiction-therapy|addiction-therapists-counselors"
    "|anxiety-disorder-treatment|cbt-therapy|ocd-treatment|personality-disorder-treatment"
    "|trauma-disorder-treatment"
)

MHD = SiteConfig(
    id="mhd",
    name="Inpatient Mental Health Finder",
    base_url="https://inpatientmentalhealthfinder.com",
    sitemap_index_url="https://inpatientmentalhealthfinder.com/sitemap_index.xml",
    geo_url_regex=re.compile(
        rf"^/serving/(?P<state>{_SLUG})(/(?P<county>{_SLUG}))?(/(?P<city>{_SLUG}))?/?$"
    ),
    # Topic pages use a TWO-LETTER state abbr and may carry a region segment before the
    # county: /personality-disorder-treatment/fl/south/palm-beach/lantana/. The optional
    # region is consumed by (?P<region>…) and discarded — it is not a county.
    topic_url_regexes=(
        re.compile(
            rf"^/({_MHD_TOPICS})/(?P<state>{_ABBR})"
            rf"(/(?P<region>{_SLUG}))?(/(?P<county>{_SLUG}))(/(?P<city>{_SLUG}))/?$"
        ),
        re.compile(
            rf"^/({_MHD_TOPICS})/(?P<state>{_ABBR})"
            rf"(/(?P<county>{_SLUG}))(/(?P<city>{_SLUG}))/?$"
        ),
        re.compile(rf"^/({_MHD_TOPICS})/(?P<state>{_ABBR})(/(?P<county>{_SLUG}))?/?$"),
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
    topic_url_regexes=(
        re.compile(
            rf"^/({_AH_TOPICS})/(?P<state>{_SLUG})"
            rf"(/(?P<county>{_SLUG}))?(/(?P<city>{_SLUG}))?/?$"
        ),
    ),
    slug_field_order=("state", "county", "city"),
)

SITES: dict[str, SiteConfig] = {MHD.id: MHD, AH.id: AH}
