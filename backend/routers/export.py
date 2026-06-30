"""On-demand export of the current filtered view to a FRESH Google Sheet (ADR-016).

The master sheet the pipeline auto-writes is never touched here — this creates a
brand-new spreadsheet. The exporter is a dependency so tests can mock the Google
call and assert it receives the correctly-filtered rows.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from authority_finder.config import get_settings
from authority_finder.db.ingest import prospect_to_output_row
from authority_finder.db.repository import get_prospects
from authority_finder.output.sheet_export import SheetExporter
from backend.deps import SessionDep
from backend.schemas import ExportOut, ExportRequest

router = APIRouter(prefix="/export", tags=["export"])


def get_exporter() -> SheetExporter:
    settings = get_settings()
    return SheetExporter(
        credentials_path=settings.google_sheets_credentials_path,
        spreadsheet_id=settings.export_sheet_id or settings.google_sheet_id,
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
