"""Topic-prefixed geo URLs (ADR-031).

Both sites publish geo pages under content-type prefixes that the original patterns never
matched, and an unmatched URL simply returned None — indistinguishable from "not a geo page".
That hid 9 AH pages and 2,848 MHD pages.

Real URLs, taken from the live sitemaps:
    AH   /support-groups/california/orange-county/
         /drug-rehab-centers/california/palos-verdes/
    MHD  /outpatient-treatment/ca/southern/
         /ocd-treatment/tn/davidson-county/nashville/
         /personality-disorder-treatment/fl/south/palm-beach/lantana/

Note MHD's topic pages use a TWO-LETTER state abbreviation, unlike /serving/ which uses the
full slug — so the ADR-004 whitelist rejected them even where the shape matched.
"""

from datetime import UTC, datetime

from authority_finder.geo_monitor.models import GeoPage, SiteConfig
from authority_finder.geo_monitor.sites import AH, MHD
from authority_finder.geo_monitor.url_parser import parse_geo_url

NOW = datetime(2026, 8, 4, tzinfo=UTC)


def _p(url: str, site: SiteConfig) -> GeoPage | None:
    return parse_geo_url(url, site, now=NOW)


class TestAhTopicPrefixes:
    def test_support_groups_county(self) -> None:
        g = _p("https://addictionhotline.com/support-groups/california/orange-county/", AH)
        assert g is not None
        assert g.state == "california"
        assert g.level == "county"

    def test_drug_rehab_centers_city(self) -> None:
        g = _p("https://addictionhotline.com/drug-rehab-centers/california/palos-verdes/", AH)
        assert g is not None
        assert g.state == "california"

    def test_topic_state_only(self) -> None:
        g = _p("https://addictionhotline.com/support-groups/california/", AH)
        assert g is not None
        assert g.level == "state"

    def test_the_plain_pattern_still_works(self) -> None:
        g = _p("https://addictionhotline.com/wyoming/", AH)
        assert g is not None and g.level == "state"

    def test_a_non_geo_topic_page_is_still_rejected(self) -> None:
        """/review-us/ryan-h/ must not parse as state='review-us'."""
        assert _p("https://addictionhotline.com/review-us/ryan-h/", AH) is None


class TestMhdTopicPrefixes:
    def test_abbreviated_state_is_expanded(self) -> None:
        g = _p("https://inpatientmentalhealthfinder.com/outpatient-treatment/ca/southern/", MHD)
        assert g is not None
        assert g.state == "california", "two-letter abbr must expand to the full slug"

    def test_county_and_city(self) -> None:
        g = _p(
            "https://inpatientmentalhealthfinder.com/ocd-treatment/tn/davidson-county/nashville/",
            MHD,
        )
        assert g is not None
        assert g.state == "tennessee"
        assert g.city == "nashville"
        assert g.level == "city"

    def test_region_segment_is_dropped_not_mistaken_for_a_county(self) -> None:
        """/fl/south/palm-beach/lantana/ — 'south' is a region, the county is palm-beach."""
        g = _p(
            "https://inpatientmentalhealthfinder.com/"
            "personality-disorder-treatment/fl/south/palm-beach/lantana/",
            MHD,
        )
        assert g is not None
        assert g.state == "florida"
        assert g.county == "palm-beach"
        assert g.city == "lantana"

    def test_serving_pattern_still_works(self) -> None:
        g = _p("https://inpatientmentalhealthfinder.com/serving/florida/sumter/leesburg/", MHD)
        assert g is not None
        assert (g.state, g.county, g.city) == ("florida", "sumter", "leesburg")

    def test_a_plain_about_page_is_still_rejected(self) -> None:
        assert _p("https://inpatientmentalhealthfinder.com/meet-the-team/", MHD) is None

    def test_facility_pages_are_not_geo_pages(self) -> None:
        assert (
            _p("https://inpatientmentalhealthfinder.com/facilites/sage-medical-clinic/", MHD)
            is None
        )
