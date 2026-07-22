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
_GEO_COL = 7  # "Geo Served" index in OUTPUT_HEADER (after the Contact Source/Trust columns)
_RANGE = "A:M"

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

    async def write(
        self, rows: list[OutputRow], *, replace: bool = False, allow_shrink: bool = False
    ) -> SheetsWriteResult:
        """Append new (deduped) rows; ``replace=True`` rewrites the whole tab in place.

        A destructive rewrite that would SHRINK the tab is refused unless ``allow_shrink=True``
        (ADR-025): a client editing the header, or a short run, must never wipe the deliverable.
        Runs the sync google client off the event loop.
        """
        if not self._sheet_id:
            raise SheetsError("GOOGLE_SHEET_ID is not set")
        if not self._creds_path.exists():
            raise SheetsError(f"service-account file not found: {self._creds_path}")
        return await asyncio.to_thread(self._write_sync, rows, replace, allow_shrink)

    def _write_sync(
        self, rows: list[OutputRow], replace: bool, allow_shrink: bool
    ) -> SheetsWriteResult:
        values_api: Any = self._service().spreadsheets().values()
        existing = self._read(values_api)
        final = dedupe_and_sort(rows)

        # Full rewrite when explicitly replacing (value corrections that append can't apply)
        # or migrating an older column layout (mixing layouts would break dedup). A drifted
        # header ALSO lands here — which is exactly why the shrink guard below is essential.
        schema_changed = bool(existing) and existing[0] != OUTPUT_HEADER
        if replace or schema_changed:
            return self._safe_rewrite(
                values_api,
                final,
                existing,
                allow_shrink=allow_shrink,
                reason="replace" if replace else "migration",
            )

        header_written = self._ensure_header(values_api, existing)
        existing_keys = _existing_keys(existing)
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

    def _safe_rewrite(
        self,
        values_api: Any,
        final: list[OutputRow],
        existing: list[list[str]],
        *,
        allow_shrink: bool,
        reason: str,
    ) -> SheetsWriteResult:
        """Rewrite the tab from A1 without a destructive clear-first window (ADR-025).

        Refuses a rewrite that would leave FEWER rows than the tab currently holds (a client
        edited the header, or a truncated run) unless ``allow_shrink`` — so normal use can never
        wipe the master deliverable. Writes in place from A1 (overwriting the old rows, no empty
        window), then clears only the trailing band when the new data is genuinely shorter.
        """
        existing_data_rows = max(0, len(existing) - 1)  # rows under whatever header is there
        if len(final) < existing_data_rows and not allow_shrink:
            raise SheetsError(
                f"refusing to rewrite {self._tab}: it holds {existing_data_rows} rows but the "
                f"write has only {len(final)} — this would shrink/wipe the deliverable (the tab "
                f"may have been edited). Pass allow_shrink=True to force an intentional correction."
            )
        body_rows = [OUTPUT_HEADER, *(r.cells() for r in final)]
        self._call(
            values_api.update(
                spreadsheetId=self._sheet_id,
                range=f"{self._tab}!A1",
                valueInputOption="RAW",
                body={"values": body_rows},
            )
        )
        if len(body_rows) < len(existing):
            # Old rows extend past the new data — clear only that trailing band.
            self._call(
                values_api.clear(
                    spreadsheetId=self._sheet_id,
                    range=f"{self._tab}!A{len(body_rows) + 1}:Z",
                    body={},
                )
            )
        _log.warning("sheets.full_rewrite", rewrote=len(final), reason=reason)
        return SheetsWriteResult(appended=len(final), skipped_existing=0, header_written=True)

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
