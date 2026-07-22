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


async def test_search_default_order_and_server_side_sort(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed(session, website="uwyo.edu", geo="Wyoming", trust=TrustBand.high)
    await _seed(session, website="alaska.edu", geo="Alaska", trust=TrustBand.low)
    await _seed(session, website="nau.edu", geo="Arizona", trust=TrustBand.medium)

    # server-side search finds the row regardless of which page it's on (ADR-025)
    hit = await client.get("/prospects", params={"search": "uwyo"})
    assert [p["website"] for p in hit.json()["items"]] == ["uwyo.edu"]
    assert hit.json()["total"] == 1

    # default order is trust-first (high → medium → low), not geo-alphabetical
    default = await client.get("/prospects")
    assert [p["contact_trust"] for p in default.json()["items"]] == ["high", "medium", "low"]

    # explicit sort hits the API and orders the WHOLE dataset
    by_site = await client.get("/prospects", params={"sort": "website", "sort_dir": "asc"})
    assert [p["website"] for p in by_site.json()["items"]] == ["alaska.edu", "nau.edu", "uwyo.edu"]


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


async def test_prospect_defaults_to_not_contacted(
    client: AsyncClient, session: AsyncSession
) -> None:
    pid = await _seed(session, website="x.gov")
    row = (await client.get(f"/prospects/{pid}")).json()
    assert row["outreach_status"] == "not_contacted"
    assert row["outreach_notes"] == ""
    assert row["contacted_at"] is None


async def test_patch_outreach_updates_and_records_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    pid = await _seed(session, website="x.gov")
    resp = await client.patch(
        f"/prospects/{pid}/outreach", json={"status": "contacted", "notes": "called the director"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outreach_status"] == "contacted"
    assert body["outreach_notes"] == "called the director"
    assert body["outreach_updated_by"] == "test@authorityscout.dev"  # the fixture's signed-in user
    assert body["contacted_at"] is not None
    # persisted
    assert (await client.get(f"/prospects/{pid}")).json()["outreach_status"] == "contacted"


async def test_filter_by_outreach_status(client: AsyncClient, session: AsyncSession) -> None:
    p1 = await _seed(session, website="a.gov", geo="G1")
    await _seed(session, website="b.gov", geo="G2")
    await client.patch(f"/prospects/{p1}/outreach", json={"status": "responded"})

    responded = (await client.get("/prospects", params={"outreach_status": "responded"})).json()
    assert [p["website"] for p in responded["items"]] == ["a.gov"]
    fresh = (await client.get("/prospects", params={"outreach_status": "not_contacted"})).json()
    assert [p["website"] for p in fresh["items"]] == ["b.gov"]


async def test_patch_outreach_404(client: AsyncClient) -> None:
    resp = await client.patch("/prospects/999999/outreach", json={"status": "contacted"})
    assert resp.status_code == 404
