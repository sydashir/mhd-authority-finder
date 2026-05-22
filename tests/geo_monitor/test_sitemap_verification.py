"""Live Playwright verification of randomly-sampled discovered geo URLs.

For each site, fetch + parse the full geo URL list, sample three with a fixed
RNG seed (so re-runs hit the same URLs unless the sitemaps changed), and
navigate to each with headless chromium. Verifies HTTP 200, no silent redirect
to the homepage / non-geo path, and that the page's ``<title>`` or first
``<h1>`` references the expected slug.

Sitemap drift (404s, redirects, missing geo content) is *expected* on a live
site. The test always passes once it has results — it just records the rate.
"""

import json
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from playwright.async_api import Browser, Page, async_playwright

from authority_finder.geo_monitor.models import GeoPage, SiteConfig
from authority_finder.geo_monitor.sitemap_fetcher import SitemapFetcher
from authority_finder.geo_monitor.sites import SITES
from authority_finder.geo_monitor.url_parser import parse_geo_url

SAMPLE_SEED = 42
SAMPLE_PER_SITE = 3
NAV_TIMEOUT_MS = 15_000
FINDINGS_PATH = Path("data/playwright_findings.json")


@dataclass
class Finding:
    site_id: str
    url: str
    expected_slug: str
    status: int | None
    final_url: str
    title: str
    h1: str | None
    ok: bool
    issues: list[str]


@pytest.mark.live
async def test_random_geo_urls_verify_with_chromium() -> None:
    rng = random.Random(SAMPLE_SEED)
    now = datetime.now(UTC)

    samples: list[tuple[SiteConfig, GeoPage]] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        fetcher = SitemapFetcher(client=client)
        for config in SITES.values():
            entries = await fetcher.fetch_all_geo_entries(config)
            pages = [
                p
                for entry in entries
                if (p := parse_geo_url(entry.loc, config, now=now)) is not None
            ]
            assert pages, f"{config.id} returned zero parseable geo pages"
            picked = rng.sample(pages, k=min(SAMPLE_PER_SITE, len(pages)))
            samples.extend((config, p) for p in picked)

    findings: list[Finding] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for config, geo_page in samples:
                finding = await _verify_one(browser, config, geo_page)
                findings.append(finding)
        finally:
            await browser.close()

    _write_findings_sync(now, findings)

    passing = sum(1 for f in findings if f.ok)
    print(f"\nplaywright verification: {passing}/{len(findings)} clean (seed={SAMPLE_SEED})")
    for f in findings:
        marker = "OK" if f.ok else "FAIL"
        print(f"  [{marker}] {f.site_id} {f.url} -> {f.status} ({'; '.join(f.issues) or 'clean'})")

    assert findings, "expected non-empty sample"


def _write_findings_sync(now: datetime, findings: list[Finding]) -> None:
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINDINGS_PATH.write_text(
        json.dumps(
            {
                "seed": SAMPLE_SEED,
                "verified_at": now.isoformat(),
                "findings": [asdict(f) for f in findings],
            },
            indent=2,
        )
    )


async def _verify_one(browser: Browser, config: SiteConfig, geo_page: GeoPage) -> Finding:
    expected_slug = geo_page.city or geo_page.county or geo_page.state
    expected_phrase = expected_slug.replace("-", " ")

    page: Page = await browser.new_page()
    issues: list[str] = []
    status: int | None = None
    final_url = ""
    title = ""
    h1_text: str | None = None

    try:
        response = await page.goto(
            geo_page.url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded"
        )
        status = response.status if response else None
        final_url = page.url
        title = await page.title()
        try:
            h1_loc = page.locator("h1").first
            if await h1_loc.count() > 0:
                h1_text = (await h1_loc.text_content()) or ""
        except (TimeoutError, RuntimeError):
            h1_text = None

        if status != 200:
            issues.append(f"status={status}")

        if final_url.rstrip("/") == config.base_url.rstrip("/"):
            issues.append("redirected to site homepage")
        elif not config.geo_url_regex.match(final_url.replace(config.base_url, "")):
            issues.append(f"final url no longer matches geo regex: {final_url}")

        haystack = f"{title} {h1_text or ''}".lower()
        if expected_phrase.lower() not in haystack:
            issues.append(f"expected slug {expected_phrase!r} not found in title/h1")
    finally:
        await page.close()

    return Finding(
        site_id=config.id,
        url=geo_page.url,
        expected_slug=expected_slug,
        status=status,
        final_url=final_url,
        title=title,
        h1=h1_text,
        ok=not issues,
        issues=issues,
    )
