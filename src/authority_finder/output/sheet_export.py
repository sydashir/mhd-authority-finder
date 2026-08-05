"""On-demand export to a NEW TAB in a Google Sheet workbook (ADR-016).

Distinct from :class:`SheetsWriter` (which appends to the master auto-write tab):
this adds a fresh, uniquely-named tab to a workbook the service account can edit
and writes the filtered view there. The auto-write tab (``Prospects``) is never
touched. A plain service account cannot create standalone spreadsheets (no Drive
storage → 403), so a new tab in an existing workbook is the export surface; point
``EXPORT_SHEET_ID`` at a dedicated workbook to keep exports out of the master.

Sync google client → run off the event loop. Google objects are ``Any``.
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

EXPORT_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ExportResult(BaseModel):
    spreadsheet_id: str
    url: str
    row_count: int
    tab: str


class SheetExporter:
    """Writes a filtered view to a new tab in ``spreadsheet_id``; master tab untouched."""

    def __init__(self, *, credentials_path: Path, spreadsheet_id: str) -> None:
        self._creds_path = credentials_path
        self._sheet_id = spreadsheet_id

    async def export(self, rows: list[OutputRow], *, title: str) -> ExportResult:
        if not self._sheet_id:
            raise SheetsError("no export workbook configured (EXPORT_SHEET_ID or GOOGLE_SHEET_ID)")
        if not self._creds_path.exists():
            raise SheetsError(f"service-account file not found: {self._creds_path}")
        return await asyncio.to_thread(self._export_sync, rows, title)

    def _export_sync(self, rows: list[OutputRow], title: str) -> ExportResult:
        creds = _sa.Credentials.from_service_account_file(
            str(self._creds_path), scopes=EXPORT_SCOPES
        )
        sheets: Any = _discovery.build("sheets", "v4", credentials=creds, cache_discovery=False)

        added: Any = self._call(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=self._sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
            )
        )
        new_tab_id = cast("int", added["replies"][0]["addSheet"]["properties"]["sheetId"])

        self._call(
            sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._sheet_id,
                range=f"'{title}'!A1",
                valueInputOption="RAW",
                body={"values": [OUTPUT_HEADER, *(r.cells() for r in rows)]},
            )
        )
        url = f"https://docs.google.com/spreadsheets/d/{self._sheet_id}/edit#gid={new_tab_id}"
        _log.info("sheet_export.created_tab", tab=title, rows=len(rows))
        return ExportResult(spreadsheet_id=self._sheet_id, url=url, row_count=len(rows), tab=title)

    def _call(self, request: Any) -> Any:
        try:
            return request.execute()
        except Exception as exc:
            raise SheetsError(f"Sheets export failed: {exc}") from exc
