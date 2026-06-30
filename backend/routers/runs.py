"""Run history + single-run status (the UI polls this after triggering a run)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from authority_finder.db.repository import count_runs, get_run, get_runs
from backend.deps import SessionDep
from backend.schemas import PageOf, RunOut

router = APIRouter(prefix="/runs", tags=["runs"])


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


@router.get("/{run_id}", response_model=RunOut)
async def get_one(run_id: int, session: SessionDep) -> RunOut:
    row = await get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunOut.model_validate(row)
