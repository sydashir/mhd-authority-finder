"""Liveness + DB-connectivity probe."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from backend.deps import SessionDep

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthOut)
async def health(session: SessionDep, response: Response) -> HealthOut:
    """200 + database=ok when Postgres answers; 503 + database=down otherwise."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="degraded", database="down")
    return HealthOut(status="ok", database="ok")
