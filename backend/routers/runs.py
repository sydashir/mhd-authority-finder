"""Run history, single-run status (the UI polls this), and triggering a run."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from authority_finder.config import get_settings
from authority_finder.db.models import RunStatus
from authority_finder.db.repository import count_runs, create_run, get_run, get_runs
from authority_finder.geo_monitor.state import DEFAULT_STATE_DIR
from backend.deps import SessionDep, SessionmakerDep, get_sessionmaker
from backend.jobs import RunJob, RunSummary, execute_run, run_pipeline_job
from backend.schemas import PageOf, RunAccepted, RunCreate, RunOut

router = APIRouter(prefix="/runs", tags=["runs"])


def get_run_job(request: Request) -> RunJob:
    """The real pipeline job, wired with settings + the app's sessionmaker.

    A dependency so tests can override it with a mock (no scraping / no quota).
    """
    settings = get_settings()
    sessionmaker = get_sessionmaker(request)

    async def _job(run_id: int, site: str, mode: str) -> RunSummary:
        return await run_pipeline_job(
            run_id,
            site,
            mode,
            sessionmaker=sessionmaker,
            settings=settings,
            now=datetime.now(UTC),
            state_dir=DEFAULT_STATE_DIR,
        )

    return _job


RunJobDep = Annotated[RunJob, Depends(get_run_job)]


@router.get("", response_model=PageOf[RunOut])
async def list_runs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageOf[RunOut]:
    """Run history, most recent first."""
    total = await count_runs(session)
    rows = await get_runs(session, limit=limit, offset=offset)
    return PageOf[RunOut](
        items=[RunOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=RunAccepted)
async def trigger_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    sessionmaker: SessionmakerDep,
    job: RunJobDep,
) -> RunAccepted:
    """Open a run (status=running), return its id immediately, run the pipeline in the
    background. The background task writes BOTH Postgres and the Sheet and respects the
    cost rails; it finalizes the run row to success/failed when done."""
    run = await create_run(session, site=body.site)
    await session.commit()  # commit before returning so the client can poll the id
    run_id = run.id
    background_tasks.add_task(
        execute_run, sessionmaker, run_id, job, site=body.site, mode=body.mode
    )
    return RunAccepted(run_id=run_id, status=RunStatus.running)


@router.get("/{run_id}", response_model=RunOut)
async def get_one(run_id: int, session: SessionDep) -> RunOut:
    row = await get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunOut.model_validate(row)
