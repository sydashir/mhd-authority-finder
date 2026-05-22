"""Unit tests for geo_monitor pydantic models. Validation, defaults, JSON round-trips."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from authority_finder.geo_monitor.models import (
    GeoPage,
    MonitorError,
    MonitorRun,
    SitemapEntry,
    SiteState,
)


def test_geo_page_requires_known_level() -> None:
    with pytest.raises(ValidationError):
        GeoPage(
            url="https://x.example/",
            site_id="mhd",
            state="california",
            county=None,
            city=None,
            level="region",  # pyright: ignore[reportArgumentType]
            first_seen=datetime.now(UTC),
        )


def test_sitemap_entry_accepts_iso8601_lastmod_string() -> None:
    entry = SitemapEntry.model_validate({"loc": "https://x.example/a/", "lastmod": "2026-05-19"})
    assert entry.lastmod is not None
    assert entry.lastmod.year == 2026


def test_monitor_run_defaults_are_empty() -> None:
    now = datetime.now(UTC)
    run = MonitorRun(site_id="mhd", started_at=now, finished_at=now, total_pages=0)
    assert run.new_pages == []
    assert run.errors == []


def test_monitor_run_roundtrips_through_json() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)
    page = GeoPage(
        url="https://x.example/serving/california/",
        site_id="mhd",
        state="california",
        county=None,
        city=None,
        level="state",
        first_seen=now,
    )
    run = MonitorRun(
        site_id="mhd",
        started_at=now,
        finished_at=now,
        new_pages=[page],
        total_pages=1,
        errors=[MonitorError(url="https://x.example/bad/", message="boom")],
    )
    raw = run.model_dump_json()
    restored = MonitorRun.model_validate_json(raw)
    assert restored == run


def test_site_state_known_urls_serializes_as_list() -> None:
    state = SiteState(
        last_run=datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC),
        known_urls={"https://x.example/a/", "https://x.example/b/"},
    )
    raw = state.model_dump_json()
    restored = SiteState.model_validate_json(raw)
    assert restored.known_urls == state.known_urls
