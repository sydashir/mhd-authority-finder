"""The pipeline→DB bridge against real Postgres: OutputRows persist as prospects,
the run is recorded, and each prospect links to its geo (ADR-013)."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db.ingest import persist_pipeline_run
from authority_finder.db.models import Run, RunStatus, SourceTag, TrustBand
from authority_finder.db.repository import get_geos, get_prospects
from authority_finder.geo_monitor.models import GeoPage
from authority_finder.output.models import OutputRow


def _row(website: str, *, geo: str = "Orange County, California", trust: str = "high") -> OutputRow:
    return OutputRow(
        website=website,
        specific_page=f"https://{website}/behavioral-health",
        email=f"bh@{website}",
        phone="+17148341234",
        contact_source="mailto (same-domain)",
        contact_trust=trust,
        organization_description="desc",
        geo_served=geo,
        population=3165820,
        competitor_links="—",
        source_tag="MHD",
        date_added="2026-06-26",
        confidence="high",
    )


def _oc_geo() -> GeoPage:
    return GeoPage(
        url="https://inpatientmentalhealthfinder.com/serving/california/orange-county/",
        site_id="mhd",
        state="california",
        county="orange-county",
        city=None,
        level="county",
        first_seen=datetime.now(UTC),
    )


async def test_persist_pipeline_run(session: AsyncSession) -> None:
    rows = [_row("ochealthinfo.gov"), _row("uci.edu", trust="low")]
    run_id, written = await persist_pipeline_run(
        session, rows=rows, geos=[_oc_geo()], site="mhd", billed_searches=0
    )
    await session.commit()

    assert written == 2
    prospects = await get_prospects(session)
    assert {p.website for p in prospects} == {"ochealthinfo.gov", "uci.edu"}
    # string columns mapped onto enum members
    assert prospects[0].source_tag == SourceTag.MHD
    assert {p.contact_trust for p in prospects} == {TrustBand.high, TrustBand.low}
    # each prospect links to the OC geo (its label matches geo_served)
    assert all(p.geo_id is not None for p in prospects)
    assert len(await get_geos(session)) == 1

    high = await get_prospects(session, trust=TrustBand.high)
    assert [p.website for p in high] == ["ochealthinfo.gov"]

    run = await session.get(Run, run_id)
    assert run is not None
    assert run.status == RunStatus.success
    assert run.rows_written == 2
    assert run.billed_searches == 0
    assert run.geos_processed == 1
