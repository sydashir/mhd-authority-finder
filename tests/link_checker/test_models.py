"""Link-checker models: the competitor_domains summary derived from links_found."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.link_checker.models import CompetitorLink, LinkCheckResult

GEO = GeoRef(site_id="mhd", url="https://x/serving/florida/", level="state", state="florida")


def _candidate() -> CandidateSite:
    return CandidateSite(
        registrable_domain="county.gov",
        url=HttpUrl("https://county.gov/behavioral-health"),
        title="Behavioral Health",
        domain_class="gov",
        geo=GEO,
        source_queries=["q"],
        discovered_at=datetime.now(UTC),
    )


def _link(domain: str, url: str) -> CompetitorLink:
    return CompetitorLink(
        competitor_domain=domain,
        found_on_url="https://county.gov/behavioral-health",
        anchor_text="Find treatment",
        link_url=url,
    )


def test_competitor_domains_unique_sorted() -> None:
    result = LinkCheckResult(
        candidate=_candidate(),
        pages_checked=2,
        links_found=[
            _link("recovery.com", "https://recovery.com/fl"),
            _link("samhsa.gov", "https://samhsa.gov/x"),
            _link("recovery.com", "https://recovery.com/ca"),
        ],
    )
    assert result.competitor_domains == ["recovery.com", "samhsa.gov"]


def test_empty_result_defaults() -> None:
    result = LinkCheckResult(candidate=_candidate())
    assert result.links_found == []
    assert result.pages_checked == 0
    assert result.checked_ok is True
    assert result.competitor_domains == []


def _link_on(domain: str, page: str) -> CompetitorLink:
    return CompetitorLink(
        competitor_domain=domain,
        found_on_url=page,
        anchor_text="Find treatment",
        link_url=f"https://{domain}/x",
    )


class TestFoundOnPages:
    """The client-reported ucr.edu case: links real, but on the resources hop, not the
    contact page — so the sheet's Specific Page showed none and the row looked invented."""

    CONTACT = "https://counseling.ucr.edu/"
    RESOURCES = "https://counseling.ucr.edu/resources-support"

    def test_excludes_the_page_already_shown_to_the_client(self) -> None:
        result = LinkCheckResult(
            candidate=_candidate(),
            pages_checked=2,
            links_found=[
                _link_on("samhsa.gov", self.RESOURCES),
                _link_on("addictionresource.net", self.RESOURCES),
            ],
        )
        assert result.found_on_pages(exclude=self.CONTACT) == [self.RESOURCES]

    def test_blank_when_the_links_are_on_the_contact_page_itself(self) -> None:
        """Blank must mean "same page as Specific Page" — no redundant column noise."""
        result = LinkCheckResult(
            candidate=_candidate(),
            pages_checked=1,
            links_found=[_link_on("samhsa.gov", self.CONTACT)],
        )
        assert result.found_on_pages(exclude=self.CONTACT) == []

    def test_dedupes_and_sorts_multiple_pages(self) -> None:
        result = LinkCheckResult(
            candidate=_candidate(),
            pages_checked=2,
            links_found=[
                _link_on("samhsa.gov", self.RESOURCES),
                _link_on("recovery.com", self.RESOURCES),
                _link_on("rehabs.com", self.CONTACT),
            ],
        )
        assert result.found_on_pages(exclude="") == [self.CONTACT, self.RESOURCES]
