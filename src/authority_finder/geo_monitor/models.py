"""Data models for the geo_monitor component.

All models are pydantic v2 ``BaseModel``s so they get free validation and
JSON serialization. ``SiteConfig`` holds a compiled :class:`re.Pattern`; we
set ``arbitrary_types_allowed`` so pydantic accepts it. Imports stay at module
top-level (no ``from __future__ import annotations``) because pydantic v2
resolves field types eagerly at class-creation time.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

GeoLevel = Literal["state", "county", "city"]
SlugField = Literal["state", "county", "city"]


class SiteConfig(BaseModel):
    """Static per-site monitoring configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    id: str
    name: str
    base_url: str
    sitemap_index_url: str
    geo_url_regex: re.Pattern[str]
    slug_field_order: tuple[SlugField, ...]


class SitemapEntry(BaseModel):
    """One ``<url>`` (or ``<sitemap>``) entry parsed from an XML sitemap."""

    loc: str
    lastmod: datetime | None = None


class GeoPage(BaseModel):
    """A newly-discovered geo page on one of the monitored sites."""

    url: str
    site_id: str
    state: str
    county: str | None
    city: str | None
    level: GeoLevel
    first_seen: datetime


class MonitorError(BaseModel):
    """One per-URL failure recorded during a monitor run."""

    url: str
    message: str


class MonitorRun(BaseModel):
    """Result of a single ``run_monitor`` invocation for one site."""

    site_id: str
    started_at: datetime
    finished_at: datetime
    new_pages: list[GeoPage] = []
    total_pages: int
    errors: list[MonitorError] = []


class SiteState(BaseModel):
    """Persistent monitor state for a single site (serialized to JSON)."""

    last_run: datetime | None = None
    known_urls: set[str] = set()
