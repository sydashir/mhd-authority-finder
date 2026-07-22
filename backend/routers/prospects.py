"""Prospect reads + the outreach-status write (ADR-022) the team uses to work the list."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from authority_finder.db.models import GeoLevel, OutreachStatus, SourceTag, TrustBand
from authority_finder.db.repository import (
    count_prospects,
    get_prospect,
    get_prospects,
    update_outreach_status,
)
from backend.auth import CurrentUser
from backend.deps import SessionDep
from backend.schemas import OutreachUpdate, PageOf, ProspectOut

router = APIRouter(prefix="/prospects", tags=["prospects"])


@router.get("", response_model=PageOf[ProspectOut])
async def list_prospects(
    session: SessionDep,
    contact_trust: TrustBand | None = None,
    source_tag: SourceTag | None = None,
    geo: str | None = None,
    level: GeoLevel | None = None,
    outreach_status: OutreachStatus | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageOf[ProspectOut]:
    """Prospects matching the filters, paginated. ``total`` is the unpaged count.

    ``search`` matches the whole dataset (website/geo/email/description, case-insensitive) —
    not just the current page (ADR-025)."""
    total = await count_prospects(
        session,
        trust=contact_trust,
        source=source_tag,
        geo=geo,
        level=level,
        outreach=outreach_status,
        search=search,
    )
    rows = await get_prospects(
        session,
        trust=contact_trust,
        source=source_tag,
        geo=geo,
        level=level,
        outreach=outreach_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return PageOf[ProspectOut](
        items=[ProspectOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{prospect_id}", response_model=ProspectOut)
async def get_one(prospect_id: int, session: SessionDep) -> ProspectOut:
    row = await get_prospect(session, prospect_id)
    if row is None:
        raise HTTPException(status_code=404, detail="prospect not found")
    return ProspectOut.model_validate(row)


@router.patch("/{prospect_id}/outreach", response_model=ProspectOut)
async def set_outreach(
    prospect_id: int, body: OutreachUpdate, session: SessionDep, user: CurrentUser
) -> ProspectOut:
    """Set a prospect's outreach status/notes; records the signed-in user as who changed it."""
    row = await update_outreach_status(
        session, prospect_id, status=body.status, notes=body.notes, user_email=user.email
    )
    if row is None:
        raise HTTPException(status_code=404, detail="prospect not found")
    await session.commit()
    # Reload server-computed columns (updated_at onupdate=now()) — otherwise sync model_validate
    # would hit an expired attribute and attempt an async-illegal lazy refresh.
    await session.refresh(row)
    return ProspectOut.model_validate(row)
