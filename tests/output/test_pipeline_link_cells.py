"""The pipeline's mapping from a LinkCheckResult to the four new cells (ADR-039).

This is the join the field-path guard cannot see: the guard proves the columns EXIST all the
way to the database, this proves the pipeline actually puts the right values in them. The
domain_rating bug lived in exactly that gap — accepted as a parameter, never assigned.
"""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.link_checker.models import LinkCheckResult, OutboundLink
from authority_finder.pipeline import _link_class_cells  # pyright: ignore[reportPrivateUsage]

GEO = GeoRef(site_id="mhd", url="https://x/serving/california/", level="state", state="california")


def _result(*domains: str, page: str = "https://ucr.edu/resources") -> LinkCheckResult:
    return LinkCheckResult(
        candidate=CandidateSite(
            registrable_domain="ucr.edu",
            url=HttpUrl("https://ucr.edu/"),
            title="UC Riverside",
            domain_class="edu",
            geo=GEO,
            source_queries=["q"],
            discovered_at=datetime.now(UTC),
        ),
        outbound_links=[
            OutboundLink(domain=d, found_on_url=page, anchor_text=d, link_url=f"https://{d}/")
            for d in domains
        ],
    )


def test_each_class_lands_in_its_own_cell() -> None:
    cells = _link_class_cells(_result("drugrehab.com", "psychologytoday.com", "aa.org"))
    assert cells["addiction_directories"] == "drugrehab.com"
    assert cells["mental_health_directories"] == "psychologytoday.com"
    assert cells["support_groups"] == "aa.org"


def test_an_empty_class_reads_as_a_dash_and_provenance_stays_blank() -> None:
    cells = _link_class_cells(_result("weather.gov"))
    assert cells["addiction_directories"] == "—"
    assert cells["mental_health_directories"] == "—"
    assert cells["support_groups"] == "—"
    assert cells["support_groups_found_on"] == ""


def test_support_group_provenance_names_the_page() -> None:
    cells = _link_class_cells(_result("aa.org", page="https://ucr.edu/self-help"))
    assert cells["support_groups_found_on"] == "https://ucr.edu/self-help"


def test_every_outbound_domain_is_kept_including_the_unclassified() -> None:
    """The raw store is what makes a later seed widening a database pass, not a re-crawl."""
    cells = _link_class_cells(_result("aa.org", "nami.org", "weather.gov"))
    assert cells["outbound_domains"] == "aa.org; nami.org; weather.gov"


def test_domains_are_deduped_and_sorted() -> None:
    cells = _link_class_cells(_result("na.org", "aa.org", "na.org"))
    assert cells["support_groups"] == "aa.org; na.org"
    assert cells["outbound_domains"] == "aa.org; na.org"
