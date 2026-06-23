"""Google Sheets output writer (ADR-008).

One tab, append-only, idempotent: existing rows are read first and the input is
deduped against them by (Website, Geo Served), so re-running never duplicates.
The Google client is sync (httplib2-based), so the whole write runs in a worker
thread off the event loop. Failures raise a clear :class:`SheetsError` naming
the likely cause (the common one: the service account isn't shared as Editor).

Google objects are dynamically typed; they're contained behind ``Any`` and the
google imports are lazy so the CSV dry-run path never needs the dependency.
"""

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import structlog
from google.oauth2 import service_account
from googleapiclient import discovery
from pydantic import BaseModel

from authority_finder.output.csv_writer import dedupe_and_sort
from authority_finder.output.models import OUTPUT_HEADER, OutputRow

# The google client ships no type stubs; alias the modules through Any so the
# dynamic Resource/Credentials surface doesn't leak "unknown type" errors.
_sa: Any = service_account
_discovery: Any = discovery

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_WEBSITE_COL = 0
_GEO_COL = 5
_RANGE = "A:K"

_log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SheetsError(RuntimeError):
    """A Google Sheets write failed; message names the likely cause."""


class SheetsWriteResult(BaseModel):
    appended: int
    skipped_existing: int
    header_written: bool


class SheetsWriter:
    """Append-only, idempotent writer for one sheet tab."""

    def __init__(self, *, credentials_path: Path, spreadsheet_id: str, tab: str = "Sheet1") -> None:
        self._creds_path = credentials_path
        self._sheet_id = spreadsheet_id
        self._tab = tab

    async def write(self, rows: list[OutputRow]) -> SheetsWriteResult:
        """Append new (deduped) rows to the sheet; runs the sync client off-loop."""
        if not self._sheet_id:
            raise SheetsError("GOOGLE_SHEET_ID is not set")
        if not self._creds_path.exists():
            raise SheetsError(f"service-account file not found: {self._creds_path}")
        return await asyncio.to_thread(self._write_sync, rows)

    def _write_sync(self, rows: list[OutputRow]) -> SheetsWriteResult:
        values_api: Any = self._service().spreadsheets().values()
        existing = self._read(values_api)
        header_written = self._ensure_header(values_api, existing)
        existing_keys = _existing_keys(existing)

        final = dedupe_and_sort(rows)
        new_rows = [r for r in final if r.dedupe_key not in existing_keys]
        if new_rows:
            self._call(
                values_api.append(
                    spreadsheetId=self._sheet_id,
                    range=f"{self._tab}!{_RANGE}",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [r.cells() for r in new_rows]},
                )
            )
        _log.info(
            "sheets.write",
            appended=len(new_rows),
            skipped=len(final) - len(new_rows),
            header_written=header_written,
        )
        return SheetsWriteResult(
            appended=len(new_rows),
            skipped_existing=len(final) - len(new_rows),
            header_written=header_written,
        )

    def _service(self) -> Any:
        creds = _sa.Credentials.from_service_account_file(str(self._creds_path), scopes=SCOPES)
        return _discovery.build("sheets", "v4", credentials=creds, cache_discovery=False)

    def _read(self, values_api: Any) -> list[list[str]]:
        resp: Any = self._call(
            values_api.get(spreadsheetId=self._sheet_id, range=f"{self._tab}!{_RANGE}")
        )
        return cast("list[list[str]]", resp.get("values", []))

    def _ensure_header(self, values_api: Any, existing: list[list[str]]) -> bool:
        if existing and existing[0] == OUTPUT_HEADER:
            return False
        self._call(
            values_api.update(
                spreadsheetId=self._sheet_id,
                range=f"{self._tab}!A1",
                valueInputOption="RAW",
                body={"values": [OUTPUT_HEADER]},
            )
        )
        return True

    def _call(self, request: Any) -> Any:
        try:
            return request.execute()
        except Exception as exc:
            # Broad by design: any google client / network failure becomes a typed,
            # human-readable SheetsError naming the likely cause.
            raise self._map_error(exc) from exc

    def _map_error(self, exc: Exception) -> SheetsError:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == HTTPStatus.FORBIDDEN:
            return SheetsError(
                f"403 — the service account is likely not shared as Editor on sheet "
                f"{self._sheet_id} (or the Sheets API is not enabled on the project)"
            )
        if status == HTTPStatus.NOT_FOUND:
            return SheetsError(f"404 — spreadsheet id not found: {self._sheet_id}")
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            return SheetsError("429 — Sheets API quota exceeded; retry with backoff")
        return SheetsError(f"Sheets API call failed: {exc}")


def _existing_keys(existing: list[list[str]]) -> set[tuple[str, str]]:
    """(Website, Geo Served) keys of rows already in the sheet (skipping the header)."""
    keys: set[tuple[str, str]] = set()
    for row in existing[1:]:
        if len(row) > _GEO_COL:
            keys.add((row[_WEBSITE_COL], row[_GEO_COL]))
    return keys
