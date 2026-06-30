"""GET /prospects + /prospects/{id} against a real testcontainer Postgres (ADR-014):
the filtered, paginated read the React UI issues, with the deliverable's column shape.
"""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db.models import SourceTag, TrustBand
from authority_finder.db.repository import ProspectIn, upsert_prospect


async def _seed(
    session: AsyncSession,
    *,
    website: str,
    geo: str = "Orange County, California",
    trust: TrustBand = TrustBand.high,
    source: SourceTag = SourceTag.MHD,
) -> int:
    pid = await upsert_prospect(
        session,
        ProspectIn(
            website=website,
            specific_page=f"https://{website}/behavioral-health",
            email=f"bh@{website}",
            phone="+17148341234",
            contact_source="mailto (same-domain)",
            contact_trust=trust,
            organization_description="County behavioral health",
            geo_served=geo,
            population=3_165_820,
            competitor_links="—",
            source_tag=source,
            confidence=TrustBand.high,
            date_added=date(2026, 6, 30),
        ),
    )
    await session.commit()
    return pid


async def test_list_returns_items_and_total(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session, website="a.gov", geo="G1")
    await _seed(session, website="b.gov", geo="G2")

    resp = await client.get("/prospects")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {p["website"] for p in body["items"]} == {"a.gov", "b.gov"}
    assert body["limit"] == 50
    assert body["offset"] == 0
    # deliverable column shape + enum/date serialization
    row = body["items"][0]
    assert row["contact_trust"] == "high"  # TrustBand serializes to lowercase value
    assert row["source_tag"] == "MHD"  # SourceTag keeps the brand abbreviation
    assert row["date_added"] == "2026-06-30"
    assert row["population"] == 3_165_820


async def test_filter_by_trust(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session, website="hi.gov", geo="G1", trust=TrustBand.high)
    await _seed(session, website="lo.gov", geo="G2", trust=TrustBand.low)

    resp = await client.get("/prospects", params={"contact_trust": "high"})
    body = resp.json()
    assert body["total"] == 1
    assert [p["website"] for p in body["items"]] == ["hi.gov"]


async def test_filter_by_source(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session, website="m.gov", geo="G1", source=SourceTag.MHD)
    await _seed(session, website="a.gov", geo="G2", source=SourceTag.AH)

    resp = await client.get("/prospects", params={"source_tag": "AH"})
    body = resp.json()
    assert [p["website"] for p in body["items"]] == ["a.gov"]


async def test_pagination_pages_through(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session, website="a.gov", geo="G1")
    await _seed(session, website="b.gov", geo="G2")
    await _seed(session, website="c.gov", geo="G3")

    page1 = (await client.get("/prospects", params={"limit": 2, "offset": 0})).json()
    page2 = (await client.get("/prospects", params={"limit": 2, "offset": 2})).json()
    assert page1["total"] == 3  # total is the full count, not the page size
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    seen = {p["website"] for p in page1["items"]} | {p["website"] for p in page2["items"]}
    assert seen == {"a.gov", "b.gov", "c.gov"}


async def test_get_one_and_404(client: AsyncClient, session: AsyncSession) -> None:
    pid = await _seed(session, website="x.gov")

    resp = await client.get(f"/prospects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["website"] == "x.gov"

    missing = await client.get("/prospects/999999")
    assert missing.status_code == 404
