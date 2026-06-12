"""Pre-filter branch coverage. Pure, no network."""

from authority_finder.page_detector.prefilter import junk_url_reason, prefilter_candidate
from tests.page_detector.conftest import make_candidate


def test_competitor_domain_rejected() -> None:
    verdict = prefilter_candidate(make_candidate("https://www.samhsa.gov/find-help/"))
    assert verdict.domain_rejection == "competitor"


def test_competitor_matches_findtreatment() -> None:
    verdict = prefilter_candidate(make_candidate("https://findtreatment.gov/"))
    assert verdict.domain_rejection == "competitor"


def test_federal_domain_rejected() -> None:
    verdict = prefilter_candidate(make_candidate("https://www.cdc.gov/mental-health/"))
    assert verdict.domain_rejection == "federal"


def test_federal_matches_deep_subdomains() -> None:
    verdict = prefilter_candidate(
        make_candidate("https://pmc.ncbi.nlm.nih.gov/articles/PMC5980767/")
    )
    assert verdict.domain_rejection == "federal"


def test_state_gov_is_not_federal() -> None:
    verdict = prefilter_candidate(make_candidate("https://health.maryland.gov/bha/"))
    assert verdict.domain_rejection is None
    assert not verdict.url_is_junk


def test_pdf_is_junk_url_but_not_domain_rejected() -> None:
    verdict = prefilter_candidate(make_candidate("https://example.gov/report.pdf"))
    assert verdict.domain_rejection is None
    assert verdict.url_is_junk
    assert verdict.junk_detail is not None and "pdf" in verdict.junk_detail


def test_news_path_is_junk() -> None:
    assert junk_url_reason("https://example.gov/news/2026/funding-announced") is not None
    assert junk_url_reason("https://example.gov/press/release-1") is not None
    assert junk_url_reason("https://example.gov/blog/post") is not None


def test_search_results_are_junk() -> None:
    assert junk_url_reason("https://example.gov/search/?searchText=help&page=3") is not None
    assert junk_url_reason("https://example.gov/services?q=mental") is not None
    assert junk_url_reason("https://example.gov/search") is not None


def test_login_pages_are_junk() -> None:
    assert junk_url_reason("https://example.gov/login") is not None
    assert junk_url_reason("https://example.gov/portal/sign-in") is not None


def test_research_path_is_not_junk() -> None:
    assert junk_url_reason("https://example.gov/research/mental-health") is None


def test_clean_department_url_passes() -> None:
    assert junk_url_reason("https://example.gov/departments/behavioral-health/") is None


def test_prefixed_news_segments_are_junk() -> None:
    assert junk_url_reason("https://www.westcliff.edu/resources/wu-news/") is not None
    assert junk_url_reason("https://example.gov/city-blog/post") is not None
    assert junk_url_reason("https://example.gov/business/services") is None
