"""GET /runs + /runs/{id} against real Postgres (ADR-014): run history and the
single-run status the UI polls after triggering a run.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.db.models import RunStatus
from authority_finder.db.repository import create_run, finish_run


async def test_list_runs_most_recent_first(client: AsyncClient, session: AsyncSession) -> None:
    r1 = await create_run(session, site="mhd")
    await session.commit()
    r2 = await create_run(session, site="ah")
    await finish_run(
        session,
        r2.id,
        geos_processed=3,
        rows_written=12,
        billed_searches=4,
        status=RunStatus.success,
    )
    await session.commit()

    body = (await client.get("/runs")).json()
    assert body["total"] == 2
    assert [r["id"] for r in body["items"]] == [r2.id, r1.id]  # newest first
    top = body["items"][0]
    assert top["site"] == "ah"
    assert top["status"] == "success"
    assert top["rows_written"] == 12
    assert top["billed_searches"] == 4
    assert top["finished_at"] is not None


async def test_get_run_status_and_404(client: AsyncClient, session: AsyncSession) -> None:
    run = await create_run(session, site="both")
    await session.commit()

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["site"] == "both"
    assert body["status"] == "running"  # what the UI polls until done
    assert body["finished_at"] is None

    assert (await client.get("/runs/999999")).status_code == 404
