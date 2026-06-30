"""Async persistence API over the models (ADR-013), repository pattern.

Decoupled from the pipeline internals: callers pass a plain :class:`ProspectIn`
(the pipeline maps its OutputRow onto it). Functions take an ``AsyncSession`` and
do NOT commit — the caller owns the transaction (unit of work). This is the surface
the backend API (Phase B) will call to render and filter prospects.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import ColumnElement, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from authority_finder.db.models import Geo, GeoLevel, Prospect, Run, RunStatus, SourceTag, TrustBand


@dataclass(frozen=True, slots=True)
class ProspectIn:
    """A prospect to persist — the pipeline builds this from an OutputRow."""

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
    run_id: int | None = None
    geo_id: int | None = None


async def upsert_prospect(session: AsyncSession, data: ProspectIn) -> int:
    """Insert a prospect or update it in place on (website, geo_served). Returns its id.

    The DB unique constraint guarantees no duplicate — this is DB-level dedup,
    replacing the old app-level dedupe.
    """
    stmt = pg_insert(Prospect).values(
        website=data.website,
        specific_page=data.specific_page,
        email=data.email,
        phone=data.phone,
        contact_source=data.contact_source,
        contact_trust=data.contact_trust,
        organization_description=data.organization_description,
        geo_served=data.geo_served,
        population=data.population,
        competitor_links=data.competitor_links,
        source_tag=data.source_tag,
        confidence=data.confidence,
        date_added=data.date_added,
        run_id=data.run_id,
        geo_id=data.geo_id,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_prospect_website_geo",
        set_={
            "specific_page": stmt.excluded.specific_page,
            "email": stmt.excluded.email,
            "phone": stmt.excluded.phone,
            "contact_source": stmt.excluded.contact_source,
            "contact_trust": stmt.excluded.contact_trust,
            "organization_description": stmt.excluded.organization_description,
            "population": stmt.excluded.population,
            "competitor_links": stmt.excluded.competitor_links,
            "source_tag": stmt.excluded.source_tag,
            "confidence": stmt.excluded.confidence,
            "date_added": stmt.excluded.date_added,
            "run_id": stmt.excluded.run_id,
            "geo_id": stmt.excluded.geo_id,
            "updated_at": func.now(),
        },
    ).returning(Prospect.id)
    return (await session.execute(stmt)).scalar_one()


def _prospect_filters(
    *,
    trust: TrustBand | None,
    source: SourceTag | None,
    geo: str | None,
    level: GeoLevel | None,
) -> tuple[bool, list[ColumnElement[bool]]]:
    """The UI filter set as (needs Geo join, WHERE conditions) — shared by list + count."""
    conditions: list[ColumnElement[bool]] = []
    if level is not None:
        conditions.append(Geo.level == level)
    if trust is not None:
        conditions.append(Prospect.contact_trust == trust)
    if source is not None:
        conditions.append(Prospect.source_tag == source)
    if geo is not None:
        conditions.append(Prospect.geo_served == geo)
    return level is not None, conditions


async def get_prospects(
    session: AsyncSession,
    *,
    trust: TrustBand | None = None,
    source: SourceTag | None = None,
    geo: str | None = None,
    level: GeoLevel | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> Sequence[Prospect]:
    """Filtered, paginated prospect read — the query the UI will issue."""
    needs_join, conditions = _prospect_filters(trust=trust, source=source, geo=geo, level=level)
    stmt = select(Prospect)
    if needs_join:
        stmt = stmt.join(Geo, Prospect.geo_id == Geo.id)
    stmt = stmt.where(*conditions).order_by(Prospect.geo_served, Prospect.website)
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return (await session.scalars(stmt)).all()


async def count_prospects(
    session: AsyncSession,
    *,
    trust: TrustBand | None = None,
    source: SourceTag | None = None,
    geo: str | None = None,
    level: GeoLevel | None = None,
) -> int:
    """Total prospects matching the filters — pagination needs the unpaged count."""
    needs_join, conditions = _prospect_filters(trust=trust, source=source, geo=geo, level=level)
    stmt = select(func.count(Prospect.id))
    if needs_join:
        stmt = stmt.join(Geo, Prospect.geo_id == Geo.id)
    return (await session.execute(stmt.where(*conditions))).scalar_one()


async def get_prospect(session: AsyncSession, prospect_id: int) -> Prospect | None:
    """A single prospect by id, or None."""
    return await session.get(Prospect, prospect_id)


@dataclass(frozen=True, slots=True)
class ProspectStats:
    """Dataset-wide aggregates for the dashboard overview cards."""

    total: int
    high_trust: int
    with_email: int
    geos_covered: int


async def get_prospect_stats(session: AsyncSession) -> ProspectStats:
    """One round-trip of FILTER aggregates over the whole prospects table."""
    stmt = select(
        func.count(Prospect.id),
        func.count(Prospect.id).filter(Prospect.contact_trust == TrustBand.high),
        func.count(Prospect.id).filter(Prospect.email != ""),
        func.count(func.distinct(Prospect.geo_served)),
    )
    total, high, email, geos = (await session.execute(stmt)).one()
    return ProspectStats(total=total, high_trust=high, with_email=email, geos_covered=geos)


async def create_run(session: AsyncSession, *, site: str) -> Run:
    """Open a run row (status=running). Caller finishes it with :func:`finish_run`."""
    run = Run(site=site, status=RunStatus.running)
    session.add(run)
    await session.flush()  # populate run.id
    return run


async def finish_run(
    session: AsyncSession,
    run_id: int,
    *,
    geos_processed: int,
    rows_written: int,
    billed_searches: int,
    status: RunStatus,
    error_summary: str | None = None,
) -> Run:
    """Record the outcome of a run."""
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    run.finished_at = datetime.now(UTC)
    run.geos_processed = geos_processed
    run.rows_written = rows_written
    run.billed_searches = billed_searches
    run.status = status
    run.error_summary = error_summary
    await session.flush()
    return run


async def get_runs(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> Sequence[Run]:
    """Run history, most recent first — powers the UI run log."""
    stmt = select(Run).order_by(Run.started_at.desc(), Run.id.desc())
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return (await session.scalars(stmt)).all()


async def count_runs(session: AsyncSession) -> int:
    """Total recorded runs."""
    return (await session.execute(select(func.count(Run.id)))).scalar_one()


async def get_run(session: AsyncSession, run_id: int) -> Run | None:
    """A single run by id — what the UI polls after triggering."""
    return await session.get(Run, run_id)


async def upsert_geo(
    session: AsyncSession,
    *,
    url: str,
    site_id: str,
    state: str,
    county: str | None,
    city: str | None,
    level: GeoLevel,
) -> int:
    """Insert/refresh a monitored geo (unique on url); bumps last_checked. Returns its id."""
    stmt = pg_insert(Geo).values(
        url=url, site_id=site_id, state=state, county=county, city=city, level=level
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["url"],
        set_={
            "site_id": stmt.excluded.site_id,
            "state": stmt.excluded.state,
            "county": stmt.excluded.county,
            "city": stmt.excluded.city,
            "level": stmt.excluded.level,
            "last_checked": func.now(),
        },
    ).returning(Geo.id)
    return (await session.execute(stmt)).scalar_one()


async def get_geos(
    session: AsyncSession, *, site: str | None = None, level: GeoLevel | None = None
) -> Sequence[Geo]:
    """All monitored geos, optionally filtered by site / level."""
    stmt = select(Geo)
    if site is not None:
        stmt = stmt.where(Geo.site_id == site)
    if level is not None:
        stmt = stmt.where(Geo.level == level)
    return (await session.scalars(stmt.order_by(Geo.url))).all()
