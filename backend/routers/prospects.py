"""Prospect reads — the filtered, paginated query the UI issues."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from authority_finder.db.models import GeoLevel, SourceTag, TrustBand
from authority_finder.db.repository import count_prospects, get_prospect, get_prospects
from backend.deps import SessionDep
from backend.schemas import PageOf, ProspectOut

router = APIRouter(prefix="/prospects", tags=["prospects"])


@router.get("", response_model=PageOf[ProspectOut])
async def list_prospects(
    session: SessionDep,
    contact_trust: TrustBand | None = None,
    source_tag: SourceTag | None = None,
    geo: str | None = None,
    level: GeoLevel | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageOf[ProspectOut]:
    """Prospects matching the filters, paginated. ``total`` is the unpaged count."""
    total = await count_prospects(
        session, trust=contact_trust, source=source_tag, geo=geo, level=level
    )
    rows = await get_prospects(
        session,
        trust=contact_trust,
        source=source_tag,
        geo=geo,
        level=level,
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
