"""Billing-real SerpAPI smoke test — costs exactly 1 billed search per run.

Marked ``live_paid``: excluded from the default run AND from ``-m live``
(which is free sitemap traffic only). Opt in with ``pytest -m live_paid``.
"""

from pathlib import Path

import httpx
import pytest

from authority_finder.config import get_settings
from authority_finder.discovery.serpapi_client import SerpApiClient

pytestmark = pytest.mark.live_paid


async def test_google_light_returns_organic_results(tmp_path: Path) -> None:
    settings = get_settings()
    if not settings.serpapi_api_key.get_secret_value():
        pytest.skip("SERPAPI_API_KEY not set")

    async with httpx.AsyncClient(follow_redirects=True) as http:
        client = SerpApiClient(client=http, api_key=settings.serpapi_api_key, cache_dir=tmp_path)
        raw = await client.search("maryland mental health resources (site:.gov OR site:.edu)")

    assert raw.billed
    organic = raw.data["organic_results"]
    assert organic
    assert all({"position", "title", "link"} <= result.keys() for result in organic)
