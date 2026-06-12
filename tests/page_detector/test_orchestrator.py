"""detect_for_geo aggregation over a mixed candidate list. MockTransport only."""

import httpx

from authority_finder.discovery.models import DiscoveryResult
from authority_finder.page_detector.fetcher import PageFetcher
from authority_finder.page_detector.orchestrator import detect_for_geo
from tests.page_detector.conftest import ORANGE_COUNTY_GEO, html_page, make_candidate

GOOD = html_page(
    title="Behavioral Health Services | Orange County",
    h1="Behavioral Health Services",
    body="Mental health treatment for Orange County, California residents. " * 20,
    mailto=True,
)


async def test_detect_for_geo_aggregates_counts() -> None:
    good_url = "https://ochealthinfo.gov/services/behavioral-health/"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        if url == good_url:
            return httpx.Response(200, content=GOOD, headers={"content-type": "text/html"})
        return httpx.Response(404)

    discovery = DiscoveryResult(
        geo=ORANGE_COUNTY_GEO,
        candidates=[
            make_candidate(good_url, geo=ORANGE_COUNTY_GEO),
            make_candidate("https://www.samhsa.gov/find-help/", geo=ORANGE_COUNTY_GEO),
            make_candidate("https://www.cdc.gov/mental-health/", geo=ORANGE_COUNTY_GEO),
            make_candidate("https://dead.gov/page", geo=ORANGE_COUNTY_GEO),
        ],
        counts_by_class={"gov": 4, "edu": 0, "us_local": 0, "other": 0},
        queries_run=3,
        billed_searches=0,
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    result = await detect_for_geo(discovery, fetcher=PageFetcher(client=client))

    assert result.status_counts == {"detected": 1, "rejected": 2, "fetch_failed": 1}
    assert result.rejection_counts == {"competitor": 1, "federal": 1}
    assert result.confidence_counts == {"high": 1}
    assert result.fetches_used >= 1
    assert len(result.outcomes) == 4
