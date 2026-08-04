"""Systemic junk found by the S47 hand-audit of the DELIVERED dataset (ADR-034).

Every fixture below is a REAL row that shipped to the client in the 2,291-row deliverable.
The audit hand-classified a stratified sample of 225 and found 37 junk rows, 78% of them
systemic rather than long-tail. These cover the two buckets that are cheap and unambiguous.
"""

from authority_finder.authority_filter.platforms import is_platform
from authority_finder.domains import is_federal


class TestFederalLeaks:
    """Federal bodies served as a LOCAL prospect. They have no geo and never link locally."""

    def test_macpac_is_federal(self) -> None:
        # Shipped twice: served to Hawaii AND to Massachusetts.
        assert is_federal("https://www.macpac.gov/publication/access-in-brief/")

    def test_va_inspector_general_is_federal(self) -> None:
        assert is_federal("https://vaoig.gov/reports/mental-health-inspection-program/")

    def test_national_archives_is_federal(self) -> None:
        # Shipped to South Carolina as trumpwhitehouse.archives.gov.
        assert is_federal("https://trumpwhitehouse.archives.gov/briefings-statements/x/")

    def test_ntis_is_federal(self) -> None:
        # Shipped to Brea, California, pointing at a 1983 technical report.
        assert is_federal("https://ntrl.ntis.gov/NTRL/dashboard/searchResults/")

    def test_bureau_of_reclamation_is_federal(self) -> None:
        # Shipped to Port Hueneme, California.
        assert is_federal("https://www.usbr.gov/environmental/")

    def test_a_real_state_agency_is_not_federal(self) -> None:
        """The guard that matters: these additions must not catch state or county bodies."""
        for url in (
            "https://mh.alabama.gov/",
            "https://health.maryland.gov/bha/pages/help.aspx",
            "https://pinellas.gov/mental-health-substance-use-program-highlights/",
            "https://www.deschutescounty.gov/265/Health-Services",
        ):
            assert not is_federal(url), url


class TestPlatformLeaks:
    """Someone else's namespace published as the prospect's own domain."""

    def test_eggzack_is_a_platform(self) -> None:
        # Shipped for New Jersey: NJAMHAA's content on a marketing platform's domain.
        assert is_platform("njamhaanew.eggzack.com")

    def test_legistorm_is_a_platform(self) -> None:
        # Shipped for Illinois: a lobbying-data profile of a real association.
        assert is_platform("www.legistorm.com")

    def test_real_state_associations_are_untouched(self) -> None:
        for domain in (
            "cabehavioralhealth.org",
            "floridabha.org",
            "gc4recovery.org",
            "wamhsac.org",
            "sdccbh.org",
        ):
            assert not is_platform(domain), domain
