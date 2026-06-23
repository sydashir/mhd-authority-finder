"""Sheets writer: header-ensure, append-only idempotency, error mapping. Fully mocked."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from authority_finder.output.models import OUTPUT_HEADER, build_row
from authority_finder.output.sheets_writer import SheetsError, SheetsWriter
from authority_finder.population.models import PopulationResult
from tests.output.conftest import outcome

NOW = datetime(2026, 6, 19, tzinfo=UTC)


def _pop() -> PopulationResult:
    return PopulationResult(
        value=100, matched_name=None, geo_level_used=None, confidence="exact", source_dataset="x"
    )


def _row(domain: str):
    return build_row(
        outcome(domain=domain, page_url=f"https://{domain}/p"), population=_pop(), now=NOW
    )


class _Req:
    def __init__(self, fn: Any, error: Exception | None = None) -> None:
        self._fn = fn
        self._error = error

    def execute(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._fn()


class _ValuesApi:
    def __init__(self, existing: list[list[str]], error: Exception | None = None) -> None:
        self.existing = existing
        self.appended: list[list[str]] = []
        self.updated: list[list[str]] | None = None
        self.header_set: list[list[str]] | None = None
        self.cleared = False
        self._error = error

    def get(self, **_: Any) -> _Req:
        return _Req(lambda: {"values": self.existing}, self._error)

    def update(self, *, body: dict[str, Any], **_: Any) -> _Req:
        def _apply() -> dict[str, Any]:
            self.updated = body["values"]
            self.header_set = body["values"]
            return {}

        return _Req(_apply)

    def append(self, *, body: dict[str, Any], **_: Any) -> _Req:
        def _apply() -> dict[str, Any]:
            self.appended.extend(body["values"])
            return {}

        return _Req(_apply)

    def clear(self, **_: Any) -> _Req:
        def _apply() -> dict[str, Any]:
            self.cleared = True
            return {}

        return _Req(_apply)


class _Service:
    def __init__(self, values_api: _ValuesApi) -> None:
        self._v = values_api

    def spreadsheets(self) -> "_Service":
        return self

    def values(self) -> _ValuesApi:
        return self._v


def _writer(tmp_path: Path, values_api: _ValuesApi) -> SheetsWriter:
    creds = tmp_path / "service-account.json"
    creds.write_text("{}")
    writer = SheetsWriter(credentials_path=creds, spreadsheet_id="SHEET123", tab="Sheet1")
    writer._service = lambda: _Service(values_api)  # type: ignore[method-assign]
    return writer


async def test_schema_migration_clears_and_rewrites(tmp_path: Path) -> None:
    # Old 11-column layout present -> clear + full rewrite (no duplicate, no mixed layouts).
    old_header = ["Website", "Specific Page", "Email", "Phone", "Geo Served"]
    api = _ValuesApi(existing=[old_header, ["a.gov", "u", "", "", "Maryland"]])
    result = await _writer(tmp_path, api).write([_row("a.gov"), _row("b.gov")])
    assert api.cleared
    assert api.updated is not None and api.updated[0] == OUTPUT_HEADER
    assert len(api.updated) == 3  # header + 2 rows
    assert result.appended == 2
    assert api.appended == []  # rewrite via update, not append


async def test_writes_header_when_empty_and_appends(tmp_path: Path) -> None:
    api = _ValuesApi(existing=[])
    result = await _writer(tmp_path, api).write([_row("a.gov"), _row("b.gov")])
    assert not api.cleared
    assert api.header_set == [OUTPUT_HEADER]
    assert result.header_written
    assert result.appended == 2
    assert len(api.appended) == 2


async def test_skips_header_when_present(tmp_path: Path) -> None:
    api = _ValuesApi(existing=[OUTPUT_HEADER])
    result = await _writer(tmp_path, api).write([_row("a.gov")])
    assert not result.header_written
    assert result.appended == 1


async def test_idempotent_append_only_dedupe(tmp_path: Path) -> None:
    # a.gov for this geo already in the sheet -> only b.gov is new.
    existing_row = _row("a.gov").cells()
    api = _ValuesApi(existing=[OUTPUT_HEADER, existing_row])
    result = await _writer(tmp_path, api).write([_row("a.gov"), _row("b.gov")])
    assert result.appended == 1
    assert result.skipped_existing == 1
    assert api.appended[0][0] == "b.gov"


async def test_403_maps_to_editor_hint(tmp_path: Path) -> None:
    err = type("HttpError", (Exception,), {})()
    err.resp = type("R", (), {"status": 403})()  # type: ignore[attr-defined]
    api = _ValuesApi(existing=[], error=err)
    with pytest.raises(SheetsError, match="Editor"):
        await _writer(tmp_path, api).write([_row("a.gov")])


async def test_404_maps_to_bad_id(tmp_path: Path) -> None:
    err = type("HttpError", (Exception,), {})()
    err.resp = type("R", (), {"status": 404})()  # type: ignore[attr-defined]
    api = _ValuesApi(existing=[], error=err)
    with pytest.raises(SheetsError, match="not found"):
        await _writer(tmp_path, api).write([_row("a.gov")])


async def test_missing_sheet_id_raises(tmp_path: Path) -> None:
    creds = tmp_path / "service-account.json"
    creds.write_text("{}")
    writer = SheetsWriter(credentials_path=creds, spreadsheet_id="", tab="Sheet1")
    with pytest.raises(SheetsError, match="GOOGLE_SHEET_ID"):
        await writer.write([_row("a.gov")])


async def test_missing_creds_file_raises(tmp_path: Path) -> None:
    writer = SheetsWriter(
        credentials_path=tmp_path / "nope.json", spreadsheet_id="SHEET123", tab="Sheet1"
    )
    with pytest.raises(SheetsError, match="service-account file not found"):
        await writer.write([_row("a.gov")])


async def test_replace_clears_and_rewrites_existing_schema(tmp_path: Path) -> None:
    # Value correction: header already matches, but replace=True forces a full rewrite.
    api = _ValuesApi(existing=[OUTPUT_HEADER, _row("a.gov").cells()])
    result = await _writer(tmp_path, api).write([_row("a.gov"), _row("b.gov")], replace=True)
    assert api.cleared
    assert api.updated is not None and api.updated[0] == OUTPUT_HEADER
    assert len(api.updated) == 3  # header + 2 rows
    assert result.appended == 2
    assert api.appended == []
