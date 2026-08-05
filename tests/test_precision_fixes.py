"""Systemic junk found by the S47 hand-audit of the DELIVERED dataset (ADR-034).

Every fixture below is a REAL row that shipped to the client in the 2,291-row deliverable.
The audit hand-classified a stratified sample of 225 and found 37 junk rows, 78% of them
systemic rather than long-tail. These cover the two buckets that are cheap and unambiguous.
"""

from authority_finder.authority_filter.platforms import is_platform
from authority_finder.contact_extractor.extract import is_national_hotline
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

    def test_dod_national_resource_directory_is_federal(self) -> None:
        """Found by the S48 pre-send review: published as a local prospect in SIX geos."""
        assert is_federal("https://nrd.gov/")

    def test_remaining_federal_agencies_are_federal(self) -> None:
        for url in ("https://www.cbp.gov/", "https://www.epa.gov/", "https://www.noaa.gov/"):
            assert is_federal(url), url

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


class TestNationalHotlines:
    """S48 pre-send review: 15 delivered rows published a national crisis line as the
    organisation's OWN phone. The blocklist held only three numbers, tuned on a 589-row
    dataset; the deliverable is now 2,269 rows and the tail had grown.

    The client is a behavioural-health organisation. A rep cold-pitching RAINN's sexual
    assault line or the Trevor Project's LGBTQ youth line is the single most reputationally
    damaging thing this file can do, and 8 of the 15 rows carried no email, so the hotline
    was the only contact on the row.
    """

    def test_the_lines_that_shipped_are_blocked(self) -> None:
        for number, who in (
            ("+18006564673", "RAINN National Sexual Assault Hotline (shipped at HIGH trust)"),
            ("+18009506264", "NAMI HelpLine"),
            ("+18664887386", "Trevor Project"),
            ("+18009855990", "SAMHSA Disaster Distress Helpline"),
            ("+18002221222", "Poison Control"),
            ("+18004874889", "SAMHSA TTY"),
            ("+18007873224", "National Domestic Violence Hotline TTY"),
        ):
            assert is_national_hotline(number), who

    def test_the_original_three_still_block(self) -> None:
        for number in ("+18002738255", "+18006624357", "+18007997233"):
            assert is_national_hotline(number)

    def test_a_real_organisation_number_is_untouched(self) -> None:
        """The guard must not start eating ordinary local numbers."""
        for number in ("+19518275531", "+18666153047", "+13037366000", "+12136894111"):
            assert not is_national_hotline(number), number
