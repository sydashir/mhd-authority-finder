"""Dashboard overview aggregates (ADR-016) — the stat cards above the table."""

from fastapi import APIRouter

from authority_finder.db.repository import get_prospect_stats, get_runs
from backend.deps import SessionDep
from backend.schemas import RunOut, StatsOut

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsOut)
async def stats(session: SessionDep) -> StatsOut:
    s = await get_prospect_stats(session)
    runs = await get_runs(session, limit=1)
    return StatsOut(
        total_prospects=s.total,
        high_trust=s.high_trust,
        with_email=s.with_email,
        geos_covered=s.geos_covered,
        outreach=s.outreach,
        last_run=RunOut.model_validate(runs[0]) if runs else None,
    )
