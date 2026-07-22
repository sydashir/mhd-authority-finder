"""POST /runs background-execution lifecycle against real Postgres (ADR-014).

The actual pipeline (scraping/quota) is mocked via an injected job so these assert
only the job lifecycle + runs-table updates: 202 + running, then running -> done.
get_session yields fresh sessions from the test sessionmaker, so polling reflects
what the background task committed (no identity-map staleness).
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from authority_finder.config import Settings
from authority_finder.db.models import Base, RunStatus
from authority_finder.db.repository import create_run, finish_run, get_run
from backend.app import create_app
from backend.auth import AuthUser, get_current_user
from backend.jobs import RunSummary, sweep_orphan_runs
from backend.routers.runs import get_run_job

Trigger = tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]]


@pytest_asyncio.fixture
async def trigger(pg_url: str) -> AsyncGenerator[Trigger]:
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(Settings(cors_allow_origins=["http://localhost:5173"]))
    # ASGITransport skips lifespan, so set what lifespan would: a real sessionmaker.
    # get_session/get_sessionmaker then yield fresh sessions per request (no staleness),
    # so polling GET /runs/{id} reflects what the background task committed.
    app.state.sessionmaker = sm
    app.dependency_overrides[get_current_user] = lambda: AuthUser(email="test@authorityscout.dev")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, app, sm
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_trigger_returns_202_and_finishes_success(
    trigger: Trigger,
) -> None:
    client, app, _sm = trigger

    async def fake_job(_run_id: int, _site: str, _mode: str) -> RunSummary:
        return RunSummary(
            geos_processed=1, rows_written=5, billed_searches=0, aborted=False, note=None
        )

    app.dependency_overrides[get_run_job] = lambda: fake_job

    resp = await client.post("/runs", json={"site": "mhd", "mode": "incremental"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"  # returned immediately, before work finishes
    run_id = body["run_id"]

    # ASGITransport awaits background tasks, so the run is already finalized.
    detail = (await client.get(f"/runs/{run_id}")).json()
    assert detail["status"] == "success"
    assert detail["rows_written"] == 5
    assert detail["billed_searches"] == 0
    assert detail["geos_processed"] == 1
    assert detail["finished_at"] is not None


async def test_trigger_failure_marks_run_failed(
    trigger: Trigger,
) -> None:
    client, app, _sm = trigger

    async def boom_job(_run_id: int, _site: str, _mode: str) -> RunSummary:
        raise RuntimeError("pipeline blew up")

    app.dependency_overrides[get_run_job] = lambda: boom_job

    resp = await client.post("/runs", json={"site": "both"})  # mode defaults to incremental
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    detail = (await client.get(f"/runs/{run_id}")).json()
    assert detail["status"] == "failed"  # never left stuck 'running'
    assert "pipeline blew up" in (detail["error_summary"] or "")


async def test_aborted_summary_marks_run_failed(
    trigger: Trigger,
) -> None:
    client, app, _sm = trigger

    async def aborted_job(_run_id: int, _site: str, _mode: str) -> RunSummary:
        return RunSummary(
            geos_processed=0,
            rows_written=0,
            billed_searches=150,
            aborted=True,
            note="circuit breaker tripped",
        )

    app.dependency_overrides[get_run_job] = lambda: aborted_job

    run_id = (await client.post("/runs", json={"site": "mhd"})).json()["run_id"]
    detail = (await client.get(f"/runs/{run_id}")).json()
    assert detail["status"] == "failed"  # circuit-breaker abort is a failed run
    assert detail["error_summary"] == "circuit breaker tripped"


async def test_invalid_site_is_rejected(trigger: Trigger) -> None:
    client, _app, _sm = trigger
    resp = await client.post("/runs", json={"site": "nope"})
    assert resp.status_code == 422  # Literal validation


async def test_trigger_refused_while_a_run_is_in_progress(trigger: Trigger) -> None:
    # Concurrency guard (ADR-025): a run is already running — a double-click or a colliding
    # scheduler tick must be refused, not started (else duplicate rows + double SerpAPI spend).
    client, _app, sm = trigger
    async with sm() as session:
        await create_run(session, site="mhd")  # left 'running'
        await session.commit()

    resp = await client.post("/runs", json={"site": "ah", "mode": "incremental"})
    assert resp.status_code == 409
    assert "in progress" in resp.json()["detail"].lower()


async def test_trigger_refused_when_daily_budget_exhausted(trigger: Trigger) -> None:
    # Global budget ceiling (ADR-025): the day's recorded runs already spent past the cap
    # (default 320), so no new run may start — no flood can silently overspend the budget.
    client, _app, sm = trigger
    async with sm() as session:
        run = await create_run(session, site="mhd")
        await finish_run(
            session,
            run.id,
            geos_processed=1,
            rows_written=0,
            billed_searches=500,  # > the 320/day default ceiling
            status=RunStatus.success,
        )
        await session.commit()

    resp = await client.post("/runs", json={"site": "ah"})
    assert resp.status_code == 409
    assert "budget" in resp.json()["detail"].lower()


async def test_orphan_sweep_fails_stuck_running_rows(
    trigger: Trigger,
) -> None:
    _client, _app, sm = trigger
    async with sm() as session:
        run = await create_run(session, site="mhd")
        await session.commit()
        run_id = run.id

    swept = await sweep_orphan_runs(sm)
    assert swept == 1
    async with sm() as session:
        got = await get_run(session, run_id)
    assert got is not None
    assert got.status == RunStatus.failed
