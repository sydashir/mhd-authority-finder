"""US territories and DC (ADR-031).

MHD publishes /serving/ pages for these, so they are in scope. The unparsed-URL
instrumentation surfaced them — previously they returned None and vanished.

Verbatim slugs observed in MHD's live sitemap:
    guam, puerto-rico, virgin-islands, northern-mariana-islands, district-of-colombia
"""

from datetime import UTC, datetime

from authority_finder.geo_monitor.sites import MHD
from authority_finder.geo_monitor.states import US_STATE_SLUGS
from authority_finder.geo_monitor.url_parser import parse_geo_url

NOW = datetime(2026, 8, 4, tzinfo=UTC)
BASE = "https://inpatientmentalhealthfinder.com/serving"


class TestTerritoriesParse:
    def test_guam(self) -> None:
        assert parse_geo_url(f"{BASE}/guam/", MHD, now=NOW) is not None

    def test_guam_county(self) -> None:
        g = parse_geo_url(f"{BASE}/guam/guam-county/", MHD, now=NOW)
        assert g is not None and g.level == "county"

    def test_puerto_rico(self) -> None:
        assert parse_geo_url(f"{BASE}/puerto-rico/", MHD, now=NOW) is not None

    def test_virgin_islands(self) -> None:
        assert parse_geo_url(f"{BASE}/virgin-islands/", MHD, now=NOW) is not None

    def test_northern_mariana_islands(self) -> None:
        assert parse_geo_url(f"{BASE}/northern-mariana-islands/", MHD, now=NOW) is not None


class TestDcSpelling:
    def test_the_correct_spelling_parses(self) -> None:
        assert parse_geo_url(f"{BASE}/district-of-columbia/", MHD, now=NOW) is not None

    def test_the_site_typo_also_parses(self) -> None:
        """MHD publishes 'colombia' (the country) rather than 'columbia'. It is their URL;
        we accept what they publish rather than lose the page to someone else's typo."""
        assert parse_geo_url(f"{BASE}/district-of-colombia/", MHD, now=NOW) is not None

    def test_both_spellings_are_whitelisted(self) -> None:
        assert {"district-of-columbia", "district-of-colombia"} <= US_STATE_SLUGS


class TestStatesUnaffected:
    def test_the_fifty_states_still_parse(self) -> None:
        assert parse_geo_url(f"{BASE}/wyoming/", MHD, now=NOW) is not None

    def test_a_non_geo_slug_is_still_rejected(self) -> None:
        assert parse_geo_url(f"{BASE}/meet-the-team/", MHD, now=NOW) is None

    def test_whitelist_size_is_fifty_states_plus_territories(self) -> None:
        assert len(US_STATE_SLUGS) == 57, "50 states + DC (x2 spellings) + 4 territories + AS"
