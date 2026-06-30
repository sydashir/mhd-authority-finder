"""On-demand export to a FRESH Google Sheet (ADR-016).

Distinct from :class:`SheetsWriter` (which appends to the one master sheet the
pipeline auto-writes): this CREATES a brand-new spreadsheet from a filtered view
and returns its URL, so the master sheet is never touched by an export. The new
sheet is shared anyone-with-link reader so the recipient can open the URL.

Sync google client → run off the event loop. Google objects are dynamically
typed, contained behind ``Any``.
"""

import asyncio
from pathlib import Path
from typing import Any, cast

import structlog
from google.oauth2 import service_account
from googleapiclient import discovery
from pydantic import BaseModel

from authority_finder.output.models import OUTPUT_HEADER, OutputRow
from authority_finder.output.sheets_writer import SheetsError

_sa: Any = service_account
_discovery: Any = discovery

# Drive scope is needed to share the new file (Sheets-create alone leaves it SA-private).
EXPORT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_TAB = "Prospects"

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ExportResult(BaseModel):
    spreadsheet_id: str
    url: str
    row_count: int


class SheetExporter:
    """Creates a new spreadsheet from a filtered view; never touches the master sheet."""

    def __init__(self, *, credentials_path: Path) -> None:
        self._creds_path = credentials_path

    async def export(self, rows: list[OutputRow], *, title: str) -> ExportResult:
        if not self._creds_path.exists():
            raise SheetsError(f"service-account file not found: {self._creds_path}")
        return await asyncio.to_thread(self._export_sync, rows, title)

    def _export_sync(self, rows: list[OutputRow], title: str) -> ExportResult:
        creds = _sa.Credentials.from_service_account_file(
            str(self._creds_path), scopes=EXPORT_SCOPES
        )
        sheets: Any = _discovery.build("sheets", "v4", credentials=creds, cache_discovery=False)

        created: Any = self._call(
            sheets.spreadsheets().create(
                body={
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": _TAB}}],
                }
            )
        )
        sheet_id = cast("str", created["spreadsheetId"])
        url = cast("str", created["spreadsheetUrl"])

        self._call(
            sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=sheet_id,
                range=f"{_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [OUTPUT_HEADER, *(r.cells() for r in rows)]},
            )
        )
        self._share(creds, sheet_id)
        _log.info("sheet_export.created", spreadsheet_id=sheet_id, rows=len(rows))
        return ExportResult(spreadsheet_id=sheet_id, url=url, row_count=len(rows))

    def _share(self, creds: Any, sheet_id: str) -> None:
        """Anyone-with-link reader so the URL opens. Best-effort — a domain policy that
        forbids link-sharing must not fail the export (the sheet already exists)."""
        try:
            drive: Any = _discovery.build("drive", "v3", credentials=creds, cache_discovery=False)
            drive.permissions().create(
                fileId=sheet_id, body={"type": "anyone", "role": "reader"}
            ).execute()
        except Exception as exc:
            _log.warning("sheet_export.share_failed", spreadsheet_id=sheet_id, error=str(exc))

    def _call(self, request: Any) -> Any:
        try:
            return request.execute()
        except Exception as exc:
            raise SheetsError(f"Sheets export failed: {exc}") from exc
