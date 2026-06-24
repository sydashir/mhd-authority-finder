"""Link-check orchestrator: detected page + one resources hop, budget, isolation."""

from authority_finder.link_checker.orchestrator import (
    MAX_LINK_CHECK_FETCHES,
    check_links_for_candidate,
)
from tests.contact_extractor.conftest import candidate_outcome, fetcher_for, html


async def test_finds_competitor_on_detected_page() -> None:
    url = "https://county.gov/behavioral-health"
    routes = {
        url: html(
            body="x",
            links=(("Recovery.com", "https://recovery.com/fl"), ("Home", "https://county.gov/")),
        )
    }
    cand = candidate_outcome(url).candidate
    result = await check_links_for_candidate(cand, url, fetcher=fetcher_for(routes))
    assert result.checked_ok
    assert result.pages_checked == 1
    assert result.competitor_domains == ["recovery.com"]


async def test_finds_competitor_via_resources_hop() -> None:
    url = "https://county.gov/behavioral-health"
    resources = "https://county.gov/community-resources"
    routes = {
        url: html(body="x", links=(("Community Resources", resources),)),
        resources: html(body="y", links=(("SAMHSA", "https://www.samhsa.gov/find-help"),)),
    }
    counter: list[str] = []
    cand = candidate_outcome(url).candidate
    result = await check_links_for_candidate(cand, url, fetcher=fetcher_for(routes, counter))
    assert result.competitor_domains == ["samhsa.gov"]
    assert result.pages_checked == 2
    assert len(counter) <= MAX_LINK_CHECK_FETCHES


async def test_detected_fetch_failure_is_checked_not_ok() -> None:
    cand = candidate_outcome("https://dead.gov/x").candidate
    result = await check_links_for_candidate(cand, "https://dead.gov/x", fetcher=fetcher_for({}))
    assert result.checked_ok is False
    assert result.links_found == []


async def test_dedupes_same_link_across_detected_and_resources() -> None:
    url = "https://county.gov/behavioral-health"
    resources = "https://county.gov/resources"
    comp = ("Recovery", "https://recovery.com/fl")
    routes = {
        url: html(links=(comp, ("Resources", resources))),
        resources: html(links=(comp,)),
    }
    cand = candidate_outcome(url).candidate
    result = await check_links_for_candidate(cand, url, fetcher=fetcher_for(routes))
    assert len(result.links_found) == 1
    assert result.pages_checked == 2


async def test_clean_page_yields_empty_links() -> None:
    url = "https://county.gov/behavioral-health"
    routes = {
        url: html(links=(("Home", "https://county.gov/"), ("State", "https://health.fl.gov/")))
    }
    cand = candidate_outcome(url).candidate
    result = await check_links_for_candidate(cand, url, fetcher=fetcher_for(routes))
    assert result.checked_ok
    assert result.links_found == []
