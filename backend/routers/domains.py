"""The review queue: what the learning layer PROPOSES, for a human to accept or reject.

Candidates never reach the client's sheet. This router is the only path by which a
machine-proposed domain can become something the deliverable acts on, and it always runs
through a person (ADR-040).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from authority_finder.db.repository import get_domain_stats, get_review_queue, review_domain
from backend.auth import CurrentUser
from backend.deps import SessionDep
from backend.schemas import DomainReview, DomainStatsOut, LinkDomainOut, PageOf

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("/stats", response_model=DomainStatsOut)
async def domain_stats(session: SessionDep) -> DomainStatsOut:
    return DomainStatsOut(**await get_domain_stats(session))


@router.get("/review", response_model=PageOf[LinkDomainOut])
async def review_queue(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageOf[LinkDomainOut]:
    rows, total = await get_review_queue(session, limit=limit, offset=offset)
    return PageOf[LinkDomainOut](
        items=[LinkDomainOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{domain_id}/review", response_model=LinkDomainOut)
async def submit_review(
    domain_id: int, body: DomainReview, session: SessionDep, user: CurrentUser
) -> LinkDomainOut:
    """Accept or reject one candidate. The decision is recorded against the signed-in user."""
    row = await review_domain(
        session,
        domain_id,
        approve=body.approve,
        reviewer=user.username,
        bucket=body.bucket,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="domain not found")
    await session.commit()
    await session.refresh(row)
    return LinkDomainOut.model_validate(row)
