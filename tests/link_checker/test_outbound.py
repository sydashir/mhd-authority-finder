"""Capturing EVERY outbound domain, not just the contractual 16 (ADR-039).

The client reported a page whose directory links we did not report. The cause was structural:
``find_competitor_links`` filtered to ``COMPETITOR_DOMAINS`` at capture time, so every other
outbound domain was discarded before anything was persisted. Answering "does this page link to
drugrehab.com?" then required a full re-crawl of 2,252 pages.

These tests pin the fix: capture everything once, filter afterwards. ``find_competitor_links``
must keep its exact contractual meaning — the brief's 16 and nothing else.
"""

from authority_finder.link_checker.check import (
    classified_outbound_links,
    find_competitor_links,
    find_outbound_links,
)
from authority_finder.link_checker.classify import LinkClass
from tests.link_checker.conftest import page


class TestNothingIsDiscardedAtCapture:
    def test_every_external_domain_is_returned(self) -> None:
        links = (
            ("Recovery", "https://www.recovery.com/florida"),  # one of the 16
            ("Drug Rehab", "https://www.drugrehab.com/"),  # a directory, NOT one of the 16
            ("AA", "https://www.aa.org/"),  # a support group
            ("Weather", "https://weather.gov/forecast"),  # plainly unrelated
        )
        found = find_outbound_links(page(links=links), candidate_domain="county.gov")
        assert {link.domain for link in found} == {
            "recovery.com",
            "drugrehab.com",
            "aa.org",
            "weather.gov",
        }

    def test_the_clients_missed_link_is_captured(self) -> None:
        """drugrehab.com is not one of the 16, so the old code dropped it here."""
        links = (("Drug Rehab", "https://www.drugrehab.com/rehab/california/"),)
        found = find_outbound_links(page(links=links), candidate_domain="ucr.edu")
        assert [link.domain for link in found] == ["drugrehab.com"]
        assert found[0].anchor_text == "Drug Rehab"
        assert found[0].link_url == "https://www.drugrehab.com/rehab/california/"


class TestTheSameHygieneAsTheCompetitorCheck:
    def test_own_domain_links_are_skipped(self) -> None:
        links = (("Departments", "https://county.gov/departments"), ("AA", "https://aa.org/"))
        found = find_outbound_links(page(links=links), candidate_domain="county.gov")
        assert [link.domain for link in found] == ["aa.org"]

    def test_non_http_schemes_are_skipped(self) -> None:
        links = (("Mail", "mailto:x@county.gov"), ("Call", "tel:+15551234"), ("Doc", "ftp://f/x"))
        assert find_outbound_links(page(links=links), candidate_domain="county.gov") == []

    def test_relative_hrefs_resolve_against_the_page(self) -> None:
        links = (("Directory", "//www.drugrehab.com/x"),)
        found = find_outbound_links(
            page(final_url="https://county.gov/bh", links=links), candidate_domain="county.gov"
        )
        assert found[0].link_url == "https://www.drugrehab.com/x"

    def test_repeated_links_are_deduped_by_domain_and_href(self) -> None:
        links = (
            ("AA", "https://aa.org/"),
            ("Alcoholics Anonymous", "https://aa.org/"),
            ("AA meetings", "https://aa.org/meetings"),
        )
        found = find_outbound_links(page(links=links), candidate_domain="county.gov")
        assert len(found) == 2


class TestTheContractualColumnIsUnchanged:
    """Competitor Links means the brief's 16. Widening it would change a delivered column."""

    def test_a_new_seed_does_not_leak_into_the_competitor_check(self) -> None:
        links = (
            ("Drug Rehab", "https://www.drugrehab.com/"),
            ("AA", "https://aa.org/"),
            ("Recovery", "https://recovery.com/"),
        )
        found = find_competitor_links(page(links=links), candidate_domain="county.gov")
        assert [f.competitor_domain for f in found] == ["recovery.com"]

    def test_competitor_links_are_a_subset_of_outbound_links(self) -> None:
        links = (
            ("Recovery", "https://recovery.com/fl"),
            ("Drug Rehab", "https://www.drugrehab.com/"),
            ("Weather", "https://weather.gov/"),
        )
        content = page(links=links)
        outbound = {
            link.link_url for link in find_outbound_links(content, candidate_domain="c.gov")
        }
        competitor = {f.link_url for f in find_competitor_links(content, candidate_domain="c.gov")}
        assert competitor < outbound


class TestClassification:
    def test_links_are_bucketed_and_unknowns_dropped(self) -> None:
        links = (
            ("Drug Rehab", "https://www.drugrehab.com/"),
            ("AA", "https://aa.org/"),
            ("Psychology Today", "https://www.psychologytoday.com/us/therapists"),
            ("Weather", "https://weather.gov/"),
            ("NAMI", "https://nami.org/"),  # deliberately unclassified
        )
        buckets = classified_outbound_links(
            find_outbound_links(page(links=links), candidate_domain="county.gov")
        )
        assert {c.domain for c in buckets[LinkClass.addiction_directory]} == {"drugrehab.com"}
        assert {c.domain for c in buckets[LinkClass.support_group]} == {"aa.org"}
        assert {c.domain for c in buckets[LinkClass.mental_health_directory]} == {
            "psychologytoday.com"
        }
        assert LinkClass.unknown not in buckets

    def test_an_unclassifiable_page_yields_no_buckets(self) -> None:
        links = (("Weather", "https://weather.gov/"), ("NAMI", "https://nami.org/"))
        found = find_outbound_links(page(links=links), candidate_domain="county.gov")
        assert classified_outbound_links(found) == {}
