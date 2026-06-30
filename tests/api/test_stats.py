"""GET /stats — the dashboard overview aggregates (ADR-016), real Postgres."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db.models import RunStatus, SourceTag, TrustBand
from authority_finder.db.repository import ProspectIn, create_run, finish_run, upsert_prospect


async def _seed(
    session: AsyncSession, *, website: str, geo: str, trust: TrustBand, email: str
) -> None:
    await upsert_prospect(
        session,
        ProspectIn(
            website=website,
            specific_page=f"https://{website}/x",
            email=email,
            phone="",
            contact_source="",
            contact_trust=trust,
            organization_description="",
            geo_served=geo,
            population=None,
            competitor_links="—",
            source_tag=SourceTag.MHD,
            confidence=TrustBand.high,
            date_added=date(2026, 6, 30),
        ),
    )
    await session.commit()


async def test_stats_reflects_real_data(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session, website="a.gov", geo="G1", trust=TrustBand.high, email="a@a.gov")
    await _seed(session, website="b.gov", geo="G2", trust=TrustBand.low, email="")
    await _seed(session, website="c.gov", geo="G1", trust=TrustBand.medium, email="c@c.gov")
    run = await create_run(session, site="both")
    await finish_run(
        session,
        run.id,
        geos_processed=2,
        rows_written=3,
        billed_searches=0,
        status=RunStatus.success,
    )
    await session.commit()

    body = (await client.get("/stats")).json()
    assert body["total_prospects"] == 3
    assert body["high_trust"] == 1
    assert body["with_email"] == 2
    assert body["geos_covered"] == 2
    assert body["last_run"]["status"] == "success"
    assert body["last_run"]["rows_written"] == 3


async def test_stats_empty_dataset(client: AsyncClient) -> None:
    body = (await client.get("/stats")).json()
    assert body["total_prospects"] == 0
    assert body["high_trust"] == 0
    assert body["last_run"] is None  # no runs yet
