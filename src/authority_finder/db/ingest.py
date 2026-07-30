"""Bridge: persist a completed pipeline run to the DB (ADR-013).

The one module that knows BOTH the pipeline's output shape (:class:`OutputRow`,
:class:`GeoPage`) and the repository — it maps OutputRow → :class:`ProspectIn` so
the repository stays pipeline-agnostic. Takes a session and does NOT commit (the
caller owns the transaction).
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db import repository as repo
from authority_finder.db.models import GeoLevel, Prospect, RunStatus, SourceTag, TrustBand
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.output.models import OutputRow, geo_served_label


def prospect_to_output_row(p: Prospect) -> OutputRow:
    """Reverse of the ingest mapping: a persisted prospect back to the deliverable
    row shape, so an export produces the same columns as the master sheet."""
    return OutputRow(
        website=p.website,
        specific_page=p.specific_page,
        email=p.email,
        phone=p.phone,
        contact_source=p.contact_source,
        contact_trust=p.contact_trust.value,
        organization_description=p.organization_description,
        geo_served=p.geo_served,
        population=p.population,
        competitor_links=p.competitor_links,
        domain_rating=p.domain_rating,
        source_tag=p.source_tag.value,
        date_added=p.date_added.isoformat(),
        confidence=p.confidence.value,
    )


def _to_prospect_in(row: OutputRow, *, run_id: int, geo_id: int | None) -> repo.ProspectIn:
    return repo.ProspectIn(
        website=row.website,
        specific_page=row.specific_page,
        email=row.email,
        phone=row.phone,
        contact_source=row.contact_source,
        contact_trust=TrustBand(row.contact_trust),
        organization_description=row.organization_description,
        geo_served=row.geo_served,
        population=row.population,
        competitor_links=row.competitor_links,
        domain_rating=row.domain_rating,
        source_tag=SourceTag(row.source_tag),
        confidence=TrustBand(row.confidence),
        date_added=date.fromisoformat(row.date_added),
        run_id=run_id,
        geo_id=geo_id,
    )


async def persist_prospects(
    session: AsyncSession,
    *,
    rows: list[OutputRow],
    geos: list[GeoPage],
    run_id: int,
) -> int:
    """Upsert ``geos`` then ``rows`` (linked to ``run_id``); return rows written.

    The run row itself is the caller's concern — this only writes the geos and
    prospects, so the API can persist under a run it opened (and finishes) itself.
    The (website, geo_served) unique constraint makes prospect writes idempotent.
    """
    geo_id_by_label: dict[str, int] = {}
    for geo in geos:
        geo_id = await repo.upsert_geo(
            session,
            url=geo.url,
            site_id=geo.site_id,
            state=geo.state,
            county=geo.county,
            city=geo.city,
            level=GeoLevel(geo.level),
        )
        label = geo_served_label(level=geo.level, state=geo.state, county=geo.county, city=geo.city)
        geo_id_by_label[label] = geo_id

    for row in rows:
        await repo.upsert_prospect(
            session, _to_prospect_in(row, run_id=run_id, geo_id=geo_id_by_label.get(row.geo_served))
        )
    return len(rows)


async def persist_pipeline_run(
    session: AsyncSession,
    *,
    rows: list[OutputRow],
    geos: list[GeoPage],
    site: str,
    billed_searches: int,
) -> tuple[int, int]:
    """Persist one run end-to-end: open the run, write geos+prospects, finish it.

    Returns ``(run_id, rows_written)``. Caller commits. The API's background trigger
    instead opens/finishes its own run around :func:`persist_prospects`.
    """
    run = await repo.create_run(session, site=site)
    written = await persist_prospects(session, rows=rows, geos=geos, run_id=run.id)
    await repo.finish_run(
        session,
        run.id,
        geos_processed=len(geos),
        rows_written=len(rows),
        billed_searches=billed_searches,
        status=RunStatus.success,
    )
    return run.id, written
