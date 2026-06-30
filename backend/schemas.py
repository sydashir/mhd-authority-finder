"""Pydantic v2 response models — the API contract the React UI consumes (ADR-014).

``from_attributes`` lets these validate straight off SQLAlchemy ORM rows. Only
scalar foreign keys (``run_id``/``geo_id``) are exposed, never the lazy ``run``/
``geo`` relationships, so serialization never triggers async lazy-load I/O.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from authority_finder.db.models import GeoLevel, RunStatus, SourceTag, TrustBand


class ProspectOut(BaseModel):
    """One outreach prospect — the deliverable row shape. Enums serialize to their
    lowercase ``value`` (``TrustBand`` → ``"high"``); ``SourceTag`` keeps ``"MHD"``/``"AH"``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    website: str
    specific_page: str
    email: str
    phone: str
    contact_source: str
    contact_trust: TrustBand
    organization_description: str
    geo_served: str
    population: int | None
    competitor_links: str
    source_tag: SourceTag
    confidence: TrustBand
    date_added: date
    created_at: datetime
    updated_at: datetime
    run_id: int | None
    geo_id: int | None


class RunOut(BaseModel):
    """One pipeline run — run-history + the status the UI polls after triggering."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    geos_processed: int
    rows_written: int
    billed_searches: int
    error_summary: str | None


class GeoOut(BaseModel):
    """A monitored geo page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    site_id: str
    state: str
    county: str | None
    city: str | None
    level: GeoLevel
    first_seen: datetime
    last_checked: datetime | None


class PageOf[T](BaseModel):
    """A page of results plus the unpaged ``total`` (so the UI can render paging)."""

    items: list[T]
    total: int
    limit: int
    offset: int


class RunCreate(BaseModel):
    """Trigger body. ``incremental`` (default) processes only newly-published geos
    (cost-safe, S11); ``full`` re-runs every known geo (spends quota, circuit-broken)."""

    site: Literal["mhd", "ah", "both"]
    mode: Literal["incremental", "full"] = "incremental"


class RunAccepted(BaseModel):
    """202 response — the run_id the UI polls via GET /runs/{id}."""

    run_id: int
    status: RunStatus
