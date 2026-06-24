"""Competitor link detection — precision is the whole point (ADR-011).

A false "links to competitor" claim misleads outreach, so the substring trap,
relative-URL resolution, subdomain matching, and own-domain skip are pinned.
"""

from authority_finder.link_checker.check import find_competitor_links
from tests.link_checker.conftest import page


def test_finds_exactly_the_competitor_links_among_many() -> None:
    filler = [(f"Page {i}", f"https://county.gov/dept/{i}") for i in range(28)]
    links = (
        *filler,
        ("Recovery.com directory", "https://www.recovery.com/florida"),
        ("SAMHSA treatment locator", "https://www.samhsa.gov/find-help"),
    )
    found = find_competitor_links(page(links=links), candidate_domain="county.gov")
    assert {f.competitor_domain for f in found} == {"recovery.com", "samhsa.gov"}
    assert len(found) == 2
    by_domain = {f.competitor_domain: f for f in found}
    assert by_domain["recovery.com"].anchor_text == "Recovery.com directory"
    assert by_domain["samhsa.gov"].link_url == "https://www.samhsa.gov/find-help"


def test_substring_lookalike_not_matched() -> None:
    # rehabsomething.com must NOT match the rehabs.com competitor entry.
    links = (("Some rehab blog", "https://rehabsomething.com/florida"),)
    assert find_competitor_links(page(links=links), candidate_domain="county.gov") == []


def test_protocol_relative_competitor_link_resolved_and_matched() -> None:
    # A scheme-relative href is resolved against the page before matching.
    links = (("Directory", "//www.recovery.com/florida"),)
    found = find_competitor_links(
        page(final_url="https://county.gov/bh", links=links), candidate_domain="county.gov"
    )
    assert len(found) == 1
    assert found[0].competitor_domain == "recovery.com"
    assert found[0].link_url == "https://www.recovery.com/florida"


def test_subdomain_competitor_matched_on_registrable_domain() -> None:
    links = (("FL centers", "https://florida.rehabs.com/centers"),)
    found = find_competitor_links(page(links=links), candidate_domain="county.gov")
    assert len(found) == 1 and found[0].competitor_domain == "rehabs.com"


def test_no_competitor_links_is_clean_empty() -> None:
    links = (
        ("Home", "https://county.gov/"),
        ("State health", "https://health.florida.gov/"),
        ("Partner", "https://redcross.org/"),
    )
    assert find_competitor_links(page(links=links), candidate_domain="county.gov") == []


def test_duplicate_competitor_links_deduped() -> None:
    links = (
        ("Recovery", "https://recovery.com/fl"),
        ("Recovery again", "https://recovery.com/fl"),
    )
    found = find_competitor_links(page(links=links), candidate_domain="county.gov")
    assert len(found) == 1


def test_own_domain_link_never_flagged() -> None:
    # A candidate that itself is on a competitor domain would never reach here, but the
    # own-domain skip is explicit: self-links are not outbound competitor links.
    links = (("Our recovery program", "https://recovery.com/about"),)
    assert find_competitor_links(page(links=links), candidate_domain="recovery.com") == []
