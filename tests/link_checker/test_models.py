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
