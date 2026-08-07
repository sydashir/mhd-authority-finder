"""What the three new sheet columns read off a LinkCheckResult (ADR-039).

The result now carries EVERY outbound link, so the columns are derived views over one captured
set rather than three separate crawls. Competitor Links keeps reading only the brief's 16.
"""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.link_checker.models import CompetitorLink, LinkCheckResult, OutboundLink

GEO = GeoRef(site_id="mhd", url="https://x/serving/california/", level="state", state="california")


def _candidate() -> CandidateSite:
    return CandidateSite(
        registrable_domain="ucr.edu",
        url=HttpUrl("https://ucr.edu/"),
        title="UC Riverside",
        domain_class="edu",
        geo=GEO,
        source_queries=["q"],
        discovered_at=datetime.now(UTC),
    )


def _link(domain: str, *, page: str = "https://ucr.edu/resources") -> OutboundLink:
    return OutboundLink(
        domain=domain, found_on_url=page, anchor_text=domain, link_url=f"https://{domain}/"
    )


def _result(*domains: str, **kwargs: object) -> LinkCheckResult:
    return LinkCheckResult(
        candidate=_candidate(), outbound_links=[_link(d) for d in domains], **kwargs
    )


class TestTheThreeNewColumns:
    def test_addiction_directories_are_listed_sorted_and_unique(self) -> None:
        result = _result("drugrehab.com", "rehabs.com", "drugrehab.com", "weather.gov")
        assert result.addiction_directories == ["drugrehab.com", "rehabs.com"]

    def test_support_groups_are_listed(self) -> None:
        result = _result("aa.org", "na.org", "smartrecovery.org", "ucr.edu")
        assert result.support_groups == ["aa.org", "na.org", "smartrecovery.org"]

    def test_mental_health_directories_are_listed(self) -> None:
        assert _result("psychologytoday.com", "aa.org").mental_health_directories == [
            "psychologytoday.com"
        ]

    def test_unclassified_domains_appear_in_no_column(self) -> None:
        result = _result("nami.org", "211.org", "988lifeline.org", "weather.gov")
        assert result.addiction_directories == []
        assert result.support_groups == []
        assert result.mental_health_directories == []


class TestSupportGroupsFoundOn:
    """The client needs the page holding the links, not just the fact that they exist."""

    def test_reports_the_pages_the_groups_were_found_on(self) -> None:
        result = LinkCheckResult(
            candidate=_candidate(),
            outbound_links=[
                _link("aa.org", page="https://ucr.edu/resources"),
                _link("na.org", page="https://ucr.edu/recovery"),
                _link("weather.gov", page="https://ucr.edu/weather"),
            ],
        )
        assert result.support_groups_found_on == [
            "https://ucr.edu/recovery",
            "https://ucr.edu/resources",
        ]

    def test_is_empty_when_no_group_was_found(self) -> None:
        assert _result("weather.gov").support_groups_found_on == []


class TestTheContractualColumnIsUntouched:
    def test_competitor_domains_still_reads_only_the_sixteen(self) -> None:
        """links_found stays the filtered list; the new seeds must not leak into it."""
        result = LinkCheckResult(
            candidate=_candidate(),
            links_found=[
                CompetitorLink(
                    competitor_domain="rehabs.com",
                    found_on_url="https://ucr.edu/resources",
                    anchor_text="Rehabs",
                    link_url="https://rehabs.com/",
                )
            ],
            outbound_links=[_link("rehabs.com"), _link("drugrehab.com"), _link("aa.org")],
        )
        assert result.competitor_domains == ["rehabs.com"]


class TestTruncationIsVisible:
    def test_the_flag_defaults_off_and_is_carried_when_set(self) -> None:
        assert _result("aa.org").links_truncated is False
        assert _result("aa.org", links_truncated=True).links_truncated is True
