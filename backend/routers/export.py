"""On-demand export of the current filtered view to a FRESH Google Sheet (ADR-016).

The master sheet the pipeline auto-writes is never touched here — this creates a
brand-new spreadsheet. The exporter is a dependency so tests can mock the Google
call and assert it receives the correctly-filtered rows.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from authority_finder.config import get_settings
from authority_finder.db.ingest import prospect_to_output_row
from authority_finder.db.repository import get_prospects
from authority_finder.output.sheet_export import SheetExporter
from backend.deps import SessionDep
from backend.schemas import ExportOut, ExportRequest

router = APIRouter(prefix="/export", tags=["export"])


def resolve_export_target(*, export_id: str, master_id: str) -> str:
    """The workbook on-demand exports write into, or refuse.

    This used to fall back to the master, so every export added a tab to the workbook the
    CLIENT opens — two stale 622-row tabs were sitting beside the deliverable when it went out
    for review (ADR-035). Refusing is better than quietly writing into their file.
    """
    target = export_id.strip()
    if not target or target == master_id.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "EXPORT_SHEET_ID is not configured, or points at the master sheet. Exports add "
                "a tab to the workbook they target, so it must be a separate scratch workbook "
                "shared with the service account — never the client's deliverable."
            ),
        )
    return target


def get_exporter() -> SheetExporter:
    settings = get_settings()
    return SheetExporter(
        credentials_path=settings.google_sheets_credentials_path,
        spreadsheet_id=resolve_export_target(
            export_id=settings.export_sheet_id, master_id=settings.google_sheet_id
        ),
    )


ExporterDep = Annotated[SheetExporter, Depends(get_exporter)]


@router.post("/sheet", response_model=ExportOut)
async def export_sheet(
    body: ExportRequest, session: SessionDep, exporter: ExporterDep
) -> ExportOut:
    """Export every prospect matching the filters (not just a page) to a new sheet."""
    prospects = await get_prospects(
        session,
        trust=body.contact_trust,
        source=body.source_tag,
        geo=body.geo,
        level=body.level,
    )
    rows = [prospect_to_output_row(p) for p in prospects]
    # A unique, tab-safe title (sheet tab names can't repeat or contain : \ / ? * [ ]).
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H%M%S")
    title = body.title or f"AuthorityScout {stamp} ({len(rows)})"
    result = await exporter.export(rows, title=title)
    return ExportOut(
        url=result.url, spreadsheet_id=result.spreadsheet_id, row_count=result.row_count
    )
