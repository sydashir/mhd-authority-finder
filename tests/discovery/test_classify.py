"""Unit tests for domain classification, dedupe keys, and candidate dedup."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.discovery.classify import (
    classify_domain,
    dedupe_candidates,
    dedupe_key,
    registrable_domain,
)
from authority_finder.discovery.models import GeoRef, SearchResult

GEO = GeoRef(
    site_id="ah", url="https://addictionhotline.com/maryland/", level="state", state="maryland"
)


def test_classify_gov() -> None:
    assert classify_domain("https://health.ny.gov/diseases/") == "gov"
    assert classify_domain("https://www.ohio.gov/") == "gov"


def test_classify_edu() -> None:
    assert classify_domain("https://healthpolicy.ucla.edu/") == "edu"


def test_classify_us_local() -> None:
    assert classify_domain("https://co.orange.ca.us/probation") == "us_local"
    assert classify_domain("https://www.state.tx.us/") == "us_local"


def test_classify_other() -> None:
    assert classify_domain("https://www.ohio.org/") == "other"
    assert classify_domain("https://www.ncala.org/") == "other"


def test_registrable_domain_state_gov_collapses() -> None:
    assert registrable_domain("https://health.ny.gov/x") == "ny.gov"


def test_dedupe_key_state_portal_keeps_agency_label() -> None:
    assert dedupe_key("https://health.ny.gov/x") == "health.ny.gov"
    assert dedupe_key("https://www.dhcs.ca.gov/") == "dhcs.ca.gov"
    assert dedupe_key("https://hhs.texas.gov/") == "hhs.texas.gov"
    assert dedupe_key("https://foo.bar.ny.gov/") == "bar.ny.gov"


def test_dedupe_key_www_is_not_an_agency() -> None:
    assert dedupe_key("https://www.ca.gov/") == "ca.gov"
    assert dedupe_key("https://www.mass.gov/") == "mass.gov"


def test_dedupe_key_non_portal_gov_uses_registrable_domain() -> None:
    assert dedupe_key("https://bhsd.santaclaracounty.gov/home") == "santaclaracounty.gov"
    assert dedupe_key("https://dmh.lacounty.gov/get-help-now/") == "lacounty.gov"


def _result(position: int, link: str, query: str) -> SearchResult:
    return SearchResult(
        position=position,
        title=f"title {position}",
        link=HttpUrl(link),
        snippet="snip",
        source_query=query,
    )


def test_dedupe_merges_queries_and_keeps_best_position() -> None:
    results = [
        _result(3, "https://www.dhcs.ca.gov/services/", "q1"),
        _result(1, "https://www.dhcs.ca.gov/", "q2"),
        _result(2, "https://www.dhcs.ca.gov/", "q1"),
    ]
    now = datetime.now(UTC)
    candidates, counts = dedupe_candidates(results, geo=GEO, now=now)

    assert len(candidates) == 1
    only = candidates[0]
    assert only.registrable_domain == "dhcs.ca.gov"
    assert str(only.url) == "https://www.dhcs.ca.gov/"
    assert only.title == "title 1"
    assert only.source_queries == ["q1", "q2"]
    assert only.discovered_at == now
    assert counts == {"gov": 1, "edu": 0, "us_local": 0, "other": 0}


def test_dedupe_drops_other_but_counts_it() -> None:
    results = [
        _result(1, "https://www.ncala.org/", "q1"),
        _result(2, "https://health.maryland.gov/", "q1"),
        _result(3, "https://co.orange.ca.us/", "q1"),
    ]
    candidates, counts = dedupe_candidates(results, geo=GEO, now=datetime.now(UTC))

    assert [c.registrable_domain for c in candidates] == ["health.maryland.gov", "orange.ca.us"]
    assert [c.domain_class for c in candidates] == ["gov", "us_local"]
    assert counts == {"gov": 1, "edu": 0, "us_local": 1, "other": 1}


def test_dedupe_output_sorted_by_best_position() -> None:
    results = [
        _result(5, "https://www.umd.edu/", "q1"),
        _result(1, "https://health.maryland.gov/", "q1"),
        _result(3, "https://mha.maryland.gov/", "q1"),
    ]
    candidates, _ = dedupe_candidates(results, geo=GEO, now=datetime.now(UTC))
    assert [c.registrable_domain for c in candidates] == [
        "health.maryland.gov",
        "mha.maryland.gov",
        "umd.edu",
    ]
