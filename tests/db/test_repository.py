"""Repository layer against a REAL Postgres (ADR-013): upsert idempotency (the unique
constraint), filtered reads (what the UI will use), run lifecycle, geo upsert."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db.models import GeoLevel, RunStatus, SourceTag, TrustBand
from authority_finder.db.repository import (
    ProspectIn,
    create_run,
    finish_run,
    get_geos,
    get_prospects,
    upsert_geo,
    upsert_prospect,
)


def _prospect(
    *,
    website: str = "ochealthinfo.gov",
    geo: str = "Orange County, California",
    trust: TrustBand = TrustBand.high,
    source: SourceTag = SourceTag.MHD,
    email: str = "bh@ochealthinfo.gov",
    geo_id: int | None = None,
) -> ProspectIn:
    return ProspectIn(
        website=website,
        specific_page=f"https://{website}/behavioral-health",
        email=email,
        phone="+17148341234",
        contact_source="mailto (same-domain)",
        contact_trust=trust,
        organization_description="County behavioral health",
        geo_served=geo,
        population=3165820,
        competitor_links="—",
        source_tag=source,
        confidence=TrustBand.high,
        date_added=date(2026, 6, 26),
        geo_id=geo_id,
    )


async def test_upsert_prospect_is_idempotent_on_website_geo(session: AsyncSession) -> None:
    pid1 = await upsert_prospect(session, _prospect(email="first@ochealthinfo.gov"))
    await session.commit()
    pid2 = await upsert_prospect(session, _prospect(email="second@ochealthinfo.gov"))
    await session.commit()

    assert pid1 == pid2  # same (website, geo) → updated in place, not duplicated
    rows = await get_prospects(session)
    assert len(rows) == 1
    assert rows[0].email == "second@ochealthinfo.gov"  # latest value wins


async def test_get_prospects_filters(session: AsyncSession) -> None:
    await upsert_prospect(
        session, _prospect(website="a.gov", trust=TrustBand.high, source=SourceTag.MHD)
    )
    await upsert_prospect(
        session, _prospect(website="b.edu", trust=TrustBand.low, source=SourceTag.AH)
    )
    await session.commit()

    high = await get_prospects(session, trust=TrustBand.high)
    assert [p.website for p in high] == ["a.gov"]
    ah = await get_prospects(session, source=SourceTag.AH)
    assert [p.website for p in ah] == ["b.edu"]
    same_geo = await get_prospects(session, geo="Orange County, California")
    assert len(same_geo) == 2


async def test_run_lifecycle(session: AsyncSession) -> None:
    run = await create_run(session, site="both")
    await session.commit()
    assert run.id is not None
    assert run.status == RunStatus.running

    finished = await finish_run(
        session,
        run.id,
        geos_processed=5,
        rows_written=68,
        billed_searches=0,
        status=RunStatus.success,
    )
    await session.commit()
    assert finished.status == RunStatus.success
    assert finished.rows_written == 68
    assert finished.billed_searches == 0
    assert finished.finished_at is not None


async def test_upsert_geo_idempotent_and_filter(session: AsyncSession) -> None:
    url = "https://inpatientmentalhealthfinder.com/serving/florida/"
    g1 = await upsert_geo(
        session,
        url=url,
        site_id="mhd",
        state="florida",
        county=None,
        city=None,
        level=GeoLevel.state,
    )
    await session.commit()
    g2 = await upsert_geo(
        session,
        url=url,
        site_id="mhd",
        state="florida",
        county=None,
        city=None,
        level=GeoLevel.state,
    )
    await session.commit()
    assert g1 == g2
    assert len(await get_geos(session)) == 1
    assert len(await get_geos(session, level=GeoLevel.state)) == 1
    assert len(await get_geos(session, level=GeoLevel.city)) == 0


async def test_get_prospects_level_filter_joins_geo(session: AsyncSession) -> None:
    geo_id = await upsert_geo(
        session,
        url="https://x/serving/florida/",
        site_id="mhd",
        state="florida",
        county=None,
        city=None,
        level=GeoLevel.state,
    )
    await session.commit()
    await upsert_prospect(session, _prospect(website="fl.gov", geo="Florida", geo_id=geo_id))
    await upsert_prospect(session, _prospect(website="nogeo.gov"))  # no geo link
    await session.commit()

    state_level = await get_prospects(session, level=GeoLevel.state)
    assert [p.website for p in state_level] == ["fl.gov"]
