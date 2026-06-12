"""Data models for the discovery component.

Pydantic v2 models, mirroring the geo_monitor style: imports stay at module
top-level (no ``from __future__ import annotations``) because pydantic v2
resolves field types eagerly at class-creation time.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl

from authority_finder.geo_monitor.models import GeoLevel, GeoPage

DomainClass = Literal["gov", "edu", "us_local", "other"]


class GeoRef(BaseModel):
    """Slim reference to the geo page a discovery run serves.

    Carries only what downstream steps need to label output rows —
    deliberately not :class:`GeoPage`, which drags ``first_seen`` along.
    """

    site_id: str
    url: str
    level: GeoLevel
    state: str
    county: str | None = None
    city: str | None = None

    @classmethod
    def from_geo_page(cls, page: GeoPage) -> "GeoRef":
        return cls(
            site_id=page.site_id,
            url=page.url,
            level=page.level,
            state=page.state,
            county=page.county,
            city=page.city,
        )


class SearchResult(BaseModel):
    """One organic result from a single SerpAPI query."""

    position: int
    title: str
    link: HttpUrl
    snippet: str = ""
    source_query: str


class CandidateSite(BaseModel):
    """A deduplicated candidate domain for one geo."""

    registrable_domain: str
    url: HttpUrl
    title: str
    snippet: str = ""
    domain_class: DomainClass
    geo: GeoRef
    source_queries: list[str]
    discovered_at: datetime


class DiscoveryError(BaseModel):
    """One per-query failure recorded during a discovery run."""

    query: str
    message: str


class DiscoveryResult(BaseModel):
    """Result of running discovery for one geo.

    ``counts_by_class`` counts unique registrable domains observed per class
    *including* classes dropped from ``candidates`` (e.g. ``other``) — we
    measure what we discard before deciding whether Phase 2 needs to rescue it.
    """

    geo: GeoRef
    candidates: list[CandidateSite] = []
    counts_by_class: dict[DomainClass, int] = {}
    queries_run: int
    billed_searches: int
    errors: list[DiscoveryError] = []
