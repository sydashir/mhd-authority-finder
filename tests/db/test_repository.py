"""Repository layer against a REAL Postgres (ADR-013): upsert idempotency (the unique
constraint), filtered reads (what the UI will use), run lifecycle, geo upsert."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db.ingest import prospect_to_output_row
from authority_finder.db.models import GeoLevel, OutreachStatus, RunStatus, SourceTag, TrustBand
from authority_finder.db.repository import (
    ProspectIn,
    count_prospects,
    count_runs,
    create_run,
    finish_run,
    get_geos,
    get_prospect,
    get_prospect_stats,
    get_prospects,
    get_run,
    get_runs,
    run_rejection_reason,
    update_outreach_status,
    upsert_geo,
    upsert_prospect,
)
from authority_finder.output.csv_writer import dedupe_and_sort


def _prospect(
    *,
    website: str = "ochealthinfo.gov",
    geo: str = "Orange County, California",
    trust: TrustBand = TrustBand.high,
    source: SourceTag = SourceTag.MHD,
    links: str = "—",
    population: int | None = 3165820,
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
        population=population,
        competitor_links=links,
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


async def test_search_matches_across_fields_case_insensitive(session: AsyncSession) -> None:
    # Server-side search (ADR-025): the dashboard box must find a prospect anywhere in the set,
    # not just the loaded page. Matches website / geo / email / description, case-insensitively.
    await upsert_prospect(session, _prospect(website="uwyo.edu", geo="Wyoming", email="c@uwyo.edu"))
    await upsert_prospect(
        session, _prospect(website="alaska.edu", geo="Alaska", email="dean@alaska.edu")
    )
    await session.commit()

    assert [p.website for p in await get_prospects(session, search="uwyo")] == ["uwyo.edu"]
    assert await count_prospects(session, search="uwyo") == 1
    # case-insensitive, and matches the geo column too
    assert {p.website for p in await get_prospects(session, search="ALASKA")} == {"alaska.edu"}
    # matches email local-part
    assert {p.website for p in await get_prospects(session, search="dean@")} == {"alaska.edu"}
    assert await get_prospects(session, search="zzz-no-such-thing") == []


async def test_default_order_is_trust_first(session: AsyncSession) -> None:
    # The dashboard must open on the strongest leads (ADR-024/025), not geo-alphabetical.
    await upsert_prospect(session, _prospect(website="low.gov", geo="Alabama", trust=TrustBand.low))
    await upsert_prospect(
        session, _prospect(website="high.gov", geo="Wyoming", trust=TrustBand.high)
    )
    await upsert_prospect(
        session, _prospect(website="med.gov", geo="Nevada", trust=TrustBand.medium)
    )
    await session.commit()
    ordered = [p.contact_trust for p in await get_prospects(session)]
    assert ordered == [TrustBand.high, TrustBand.medium, TrustBand.low]


async def test_db_order_matches_the_sheet_order_exactly(session: AsyncSession) -> None:
    """The dashboard and the exported sheet must agree on "the top of the list" (ADR-038).

    Two independent implementations decide this — repository._order_by (SQL) and
    csv_writer._sort_key (Python). They have to stay identical, so this drives the SAME rows
    through both and compares. The case that used to differ, and that the client noticed:
    a medium-trust row WITH a competitor link must not outrank a high-trust row without one.
    """
    rows = [
        ("med-linked.gov", TrustBand.medium, "samhsa.gov", 9_000_000, "Texas"),
        ("high-plain.gov", TrustBand.high, "—", 1_000, "Wyoming"),
        ("low-linked.gov", TrustBand.low, "samhsa.gov", 8_000_000, "Ohio"),
        ("high-linked.gov", TrustBand.high, "samhsa.gov", 500, "Alaska"),
        ("med-plain.gov", TrustBand.medium, "—", 7_000_000, "Nevada"),
    ]
    for site, trust, links, pop, geo in rows:
        await upsert_prospect(
            session, _prospect(website=site, geo=geo, trust=trust, links=links, population=pop)
        )
    await session.commit()

    from_db = [p.website for p in await get_prospects(session)]
    from_sheet = [
        r.website
        for r in dedupe_and_sort([prospect_to_output_row(p) for p in await get_prospects(session)])
    ]
    assert from_db == from_sheet, "dashboard and sheet disagree on ordering"
    assert from_db[0] == "high-linked.gov"
    assert from_db[1] == "high-plain.gov", "a high-trust row must outrank every medium row"
    assert from_db.index("high-plain.gov") < from_db.index("med-linked.gov")


async def test_run_rejection_reason_concurrency_and_budget(session: AsyncSession) -> None:
    # The shared cost-rail gate (ADR-025) used by the API, scheduler, and CLI.
    assert await run_rejection_reason(session, max_billed_per_day=320) is None  # clean → allowed

    running = await create_run(session, site="mhd")  # a run is in progress
    await session.commit()
    concurrency = await run_rejection_reason(session, max_billed_per_day=320)
    assert concurrency is not None and "in progress" in concurrency

    # finish it having spent past the daily ceiling → now the budget blocks
    await finish_run(
        session,
        running.id,
        geos_processed=1,
        rows_written=0,
        billed_searches=400,
        status=RunStatus.success,
    )
    await session.commit()
    budget = await run_rejection_reason(session, max_billed_per_day=320)
    assert budget is not None and "budget" in budget
    # a higher ceiling lets it through again
    assert await run_rejection_reason(session, max_billed_per_day=1000) is None


async def test_pipeline_upsert_preserves_user_outreach_fields(session: AsyncSession) -> None:
    # THE make-or-break test (ADR-022): the team marks a prospect contacted with notes, then the
    # pipeline re-runs and upserts the same (website, geo) with fresh discovery data. The discovery
    # fields must UPDATE; the user-entered outreach fields must SURVIVE untouched.
    pid = await upsert_prospect(session, _prospect(email="orig@ochealthinfo.gov"))
    await session.commit()
    await update_outreach_status(
        session,
        pid,
        status=OutreachStatus.contacted,
        notes="left a voicemail",
        user_email="jake@dbh.com",
    )
    await session.commit()

    await upsert_prospect(session, _prospect(email="fresh@ochealthinfo.gov"))  # pipeline re-run
    await session.commit()

    p = await get_prospect(session, pid)
    assert p is not None
    assert p.email == "fresh@ochealthinfo.gov"  # discovery field UPDATED by the re-run
    assert p.outreach_status == OutreachStatus.contacted  # user field PRESERVED
    assert p.outreach_notes == "left a voicemail"  # PRESERVED
    assert p.outreach_updated_by == "jake@dbh.com"  # PRESERVED
    assert p.contacted_at is not None  # PRESERVED


async def test_new_prospect_defaults_to_not_contacted(session: AsyncSession) -> None:
    pid = await upsert_prospect(session, _prospect())
    await session.commit()
    p = await get_prospect(session, pid)
    assert p is not None
    assert p.outreach_status == OutreachStatus.not_contacted
    assert p.outreach_notes == ""
    assert p.contacted_at is None
    assert p.outreach_updated_by is None


async def test_update_outreach_status_records_user_and_contacted_at(session: AsyncSession) -> None:
    pid = await upsert_prospect(session, _prospect())
    await session.commit()
    p = await update_outreach_status(
        session,
        pid,
        status=OutreachStatus.contacted,
        notes="reached the director",
        user_email="a@dbh.com",
    )
    await session.commit()
    assert p is not None
    assert p.outreach_status == OutreachStatus.contacted
    assert p.outreach_notes == "reached the director"
    assert p.outreach_updated_by == "a@dbh.com"
    assert p.outreach_updated_at is not None
    assert p.contacted_at is not None  # set on first move to contacted


async def test_update_outreach_status_notes_none_keeps_existing(session: AsyncSession) -> None:
    pid = await upsert_prospect(session, _prospect())
    await session.commit()
    await update_outreach_status(
        session, pid, status=OutreachStatus.contacted, notes="my note", user_email="a@dbh.com"
    )
    await session.commit()
    # a later status change with notes=None must not wipe the note
    p = await update_outreach_status(
        session, pid, status=OutreachStatus.responded, notes=None, user_email="b@dbh.com"
    )
    await session.commit()
    assert p is not None
    assert p.outreach_status == OutreachStatus.responded
    assert p.outreach_notes == "my note"  # unchanged
    assert p.outreach_updated_by == "b@dbh.com"


async def test_update_outreach_status_missing_prospect_returns_none(session: AsyncSession) -> None:
    assert (
        await update_outreach_status(
            session, 999_999, status=OutreachStatus.contacted, notes=None, user_email="a@dbh.com"
        )
        is None
    )


async def test_get_prospects_filter_by_outreach_status(session: AsyncSession) -> None:
    p1 = await upsert_prospect(session, _prospect(website="a.gov", geo="G1"))
    await upsert_prospect(session, _prospect(website="b.gov", geo="G2"))
    await session.commit()
    await update_outreach_status(
        session, p1, status=OutreachStatus.responded, notes=None, user_email="u@dbh.com"
    )
    await session.commit()

    responded = await get_prospects(session, outreach=OutreachStatus.responded)
    assert [p.website for p in responded] == ["a.gov"]
    not_contacted = await get_prospects(session, outreach=OutreachStatus.not_contacted)
    assert [p.website for p in not_contacted] == ["b.gov"]
    assert await count_prospects(session, outreach=OutreachStatus.responded) == 1


async def test_get_prospect_stats_outreach_breakdown(session: AsyncSession) -> None:
    p1 = await upsert_prospect(session, _prospect(website="a.gov", geo="G1"))
    await upsert_prospect(session, _prospect(website="b.gov", geo="G2"))
    await session.commit()
    await update_outreach_status(
        session, p1, status=OutreachStatus.contacted, notes=None, user_email="u@dbh.com"
    )
    await session.commit()

    stats = await get_prospect_stats(session)
    assert stats.outreach["contacted"] == 1
    assert stats.outreach["not_contacted"] == 1
    assert stats.outreach["responded"] == 0  # every status present, zero-filled


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


async def test_get_prospects_pagination_and_count(session: AsyncSession) -> None:
    await upsert_prospect(session, _prospect(website="a.gov", geo="G1", trust=TrustBand.high))
    await upsert_prospect(session, _prospect(website="b.gov", geo="G2", trust=TrustBand.low))
    await upsert_prospect(session, _prospect(website="c.gov", geo="G3", trust=TrustBand.high))
    await session.commit()

    assert await count_prospects(session) == 3
    assert await count_prospects(session, trust=TrustBand.high) == 2

    first = await get_prospects(session, limit=1, offset=0)
    second = await get_prospects(session, limit=1, offset=1)
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].website != second[0].website  # distinct pages, stable order


async def test_get_prospect_by_id(session: AsyncSession) -> None:
    pid = await upsert_prospect(session, _prospect(website="x.gov"))
    await session.commit()

    found = await get_prospect(session, pid)
    assert found is not None
    assert found.website == "x.gov"
    assert await get_prospect(session, 999_999) is None


async def test_get_prospect_stats(session: AsyncSession) -> None:
    await upsert_prospect(
        session, _prospect(website="a.gov", geo="G1", trust=TrustBand.high, email="a@a.gov")
    )
    await upsert_prospect(
        session, _prospect(website="b.gov", geo="G2", trust=TrustBand.low, email="")
    )
    await upsert_prospect(
        session, _prospect(website="c.gov", geo="G1", trust=TrustBand.medium, email="c@c.gov")
    )
    await session.commit()

    stats = await get_prospect_stats(session)
    assert stats.total == 3
    assert stats.high_trust == 1
    assert stats.with_email == 2  # b.gov has no email
    assert stats.geos_covered == 2  # G1 (x2) + G2 distinct


async def test_get_runs_listing_and_count(session: AsyncSession) -> None:
    r1 = await create_run(session, site="mhd")
    await session.commit()
    r2 = await create_run(session, site="ah")
    await session.commit()

    assert await count_runs(session) == 2
    runs = await get_runs(session)
    assert [r.id for r in runs] == [r2.id, r1.id]  # most recent first

    one = await get_run(session, r1.id)
    assert one is not None
    assert one.site == "mhd"
    assert await get_run(session, 999_999) is None
