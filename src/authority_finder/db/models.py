"""SQLAlchemy 2.x async models — the Postgres source-of-truth (ADR-013).

Mirrors the pipeline's :class:`OutputRow` (the deliverable schema) as typed columns,
plus ``runs`` (pipeline-run history → run-history in the UI) and ``geos`` (the
monitored geo pages). The ``(website, geo_served)`` dedup key — previously enforced
in app code — is now a real ``UNIQUE`` constraint, so the DB itself guarantees no
duplicate prospect.

Enum columns are native Postgres enums declared once as shared :class:`sqlalchemy.Enum`
instances and reused across columns (so each ``CREATE TYPE`` is emitted exactly once).
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TrustBand(enum.Enum):
    """Shared by contact_trust and page confidence — member name == value."""

    high = "high"
    medium = "medium"
    low = "low"


class SourceTag(enum.Enum):
    MHD = "MHD"
    AH = "AH"


class RunStatus(enum.Enum):
    running = "running"
    success = "success"
    failed = "failed"


class GeoLevel(enum.Enum):
    state = "state"
    county = "county"
    city = "city"


class OutreachStatus(enum.Enum):
    """The team's workflow state for a prospect — USER-owned (ADR-022).

    The pipeline's upsert never touches this; only the outreach API mutates it.
    """

    not_contacted = "not_contacted"
    contacted = "contacted"
    responded = "responded"
    interested = "interested"
    not_interested = "not_interested"
    linked = "linked"  # they published the backlink — the goal
    bounced = "bounced"  # the contact bounced / is invalid


# One Enum instance per PG type, reused across columns → one CREATE TYPE each.
_trust_band = Enum(TrustBand, name="trust_band")
_source_tag = Enum(SourceTag, name="source_tag")
_run_status = Enum(RunStatus, name="run_status")
_geo_level = Enum(GeoLevel, name="geo_level")
_outreach_status = Enum(OutreachStatus, name="outreach_status")


class Run(Base):
    """One pipeline run — powers run-history in the UI."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    site: Mapped[str] = mapped_column(String(16))
    geos_processed: Mapped[int] = mapped_column(default=0)
    rows_written: Mapped[int] = mapped_column(default=0)
    billed_searches: Mapped[int] = mapped_column(default=0)
    status: Mapped[RunStatus] = mapped_column(_run_status, default=RunStatus.running)
    error_summary: Mapped[str | None] = mapped_column(Text)

    prospects: Mapped[list[Prospect]] = relationship(back_populates="run")


class Geo(Base):
    """A monitored geo page — replaces the JSON state files as source-of-truth."""

    __tablename__ = "geos"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(512), unique=True)
    site_id: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(64))
    county: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(64))
    level: Mapped[GeoLevel] = mapped_column(_geo_level)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    prospects: Mapped[list[Prospect]] = relationship(back_populates="geo")


class Prospect(Base):
    """One outreach prospect — every OutputRow column as a typed column."""

    __tablename__ = "prospects"
    __table_args__ = (UniqueConstraint("website", "geo_served", name="uq_prospect_website_geo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    website: Mapped[str] = mapped_column(String(255))
    specific_page: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    contact_source: Mapped[str] = mapped_column(String(64), default="")
    contact_trust: Mapped[TrustBand] = mapped_column(_trust_band)
    organization_description: Mapped[str] = mapped_column(Text, default="")
    geo_served: Mapped[str] = mapped_column(String(128))
    population: Mapped[int | None]
    competitor_links: Mapped[str] = mapped_column(Text, default="")
    # The page the contact came from, when specific_page is a different page. specific_page
    # is what the client clicks, so it holds the competitor-links page (ADR-036).
    contact_found_on: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Ahrefs DR for authority-sourced rows (ADR-027). NULL for .gov/.edu, which are never
    # scored by design — NULL means "not measured"; 0.0 would falsely claim no authority.
    domain_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_tag: Mapped[SourceTag] = mapped_column(_source_tag)
    confidence: Mapped[TrustBand] = mapped_column(_trust_band)
    date_added: Mapped[date] = mapped_column(Date)

    # USER-owned outreach fields (ADR-022) — the pipeline's upsert never touches these.
    outreach_status: Mapped[OutreachStatus] = mapped_column(
        _outreach_status,
        default=OutreachStatus.not_contacted,
        server_default=OutreachStatus.not_contacted.value,
    )
    outreach_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outreach_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outreach_updated_by: Mapped[str | None] = mapped_column(String(320))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"))
    geo_id: Mapped[int | None] = mapped_column(ForeignKey("geos.id"))

    run: Mapped[Run | None] = relationship(back_populates="prospects")
    geo: Mapped[Geo | None] = relationship(back_populates="prospects")
