"""POST /export/sheet (ADR-016): exports the filtered view to a FRESH sheet.

The Google call is mocked — these assert the endpoint selects the right filtered
rows and that the exporter builds the create/write/share calls. The real Google
call is verified live once. The master auto-write sheet is never touched: the
export path uses SheetExporter (spreadsheets.create), never SheetsWriter.append.
"""

from collections.abc import AsyncGenerator
from datetime import date
from pathlib import Path
from typing import Any

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.config import Settings
from authority_finder.db.models import SourceTag, TrustBand
from authority_finder.db.repository import ProspectIn, upsert_prospect
from authority_finder.output import sheet_export as se
from authority_finder.output.models import OUTPUT_HEADER, OutputRow
from authority_finder.output.sheet_export import ExportResult, SheetExporter
from backend.app import create_app
from backend.auth import AuthUser, get_current_user
from backend.deps import get_session
from backend.routers.export import get_exporter


class _RecordingExporter:
    def __init__(self) -> None:
        self.rows: list[OutputRow] | None = None
        self.title: str | None = None

    async def export(self, rows: list[OutputRow], *, title: str) -> ExportResult:
        self.rows = rows
        self.title = title
        return ExportResult(
            spreadsheet_id="sid123",
            url="https://docs.google.com/spreadsheets/d/sid123/edit#gid=42",
            row_count=len(rows),
            tab=title,
        )


@pytest_asyncio.fixture
async def export_setup(
    session: AsyncSession,
) -> AsyncGenerator[tuple[AsyncClient, FastAPI, _RecordingExporter]]:
    app = create_app(Settings(cors_allow_origins=["http://localhost:5173"]))
    fake = _RecordingExporter()

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_exporter] = lambda: fake
    app.dependency_overrides[get_current_user] = lambda: AuthUser(email="test@authorityscout.dev")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, app, fake
    app.dependency_overrides.clear()


async def _seed(session: AsyncSession, *, website: str, trust: TrustBand) -> None:
    await upsert_prospect(
        session,
        ProspectIn(
            website=website,
            specific_page=f"https://{website}/x",
            email=f"a@{website}",
            phone="",
            contact_source="",
            contact_trust=trust,
            organization_description="",
            geo_served="Colorado",
            population=None,
            competitor_links="—",
            source_tag=SourceTag.MHD,
            confidence=TrustBand.high,
            date_added=date(2026, 6, 30),
        ),
    )
    await session.commit()


async def test_export_only_filtered_rows_reach_exporter(
    export_setup: tuple[AsyncClient, FastAPI, _RecordingExporter],
    session: AsyncSession,
) -> None:
    client, _app, fake = export_setup
    await _seed(session, website="hi.gov", trust=TrustBand.high)
    await _seed(session, website="lo.gov", trust=TrustBand.low)

    resp = await client.post("/export/sheet", json={"contact_trust": "high"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 1
    assert body["url"] == "https://docs.google.com/spreadsheets/d/sid123/edit#gid=42"

    assert fake.rows is not None
    assert [r.website for r in fake.rows] == ["hi.gov"]  # only the high row exported
    assert fake.rows[0].contact_trust == "high"


async def test_export_all_when_no_filter(
    export_setup: tuple[AsyncClient, FastAPI, _RecordingExporter],
    session: AsyncSession,
) -> None:
    client, _app, fake = export_setup
    await _seed(session, website="hi.gov", trust=TrustBand.high)
    await _seed(session, website="lo.gov", trust=TrustBand.low)

    resp = await client.post("/export/sheet", json={})
    assert resp.json()["row_count"] == 2
    assert fake.rows is not None
    assert {r.website for r in fake.rows} == {"hi.gov", "lo.gov"}


def _output_row(website: str) -> OutputRow:
    return OutputRow(
        website=website,
        specific_page=f"https://{website}/x",
        email=f"a@{website}",
        phone="",
        contact_source="",
        contact_trust="high",
        organization_description="",
        geo_served="Colorado",
        population=None,
        competitor_links="—",
        source_tag="MHD",
        date_added="2026-06-30",
        confidence="high",
    )


class _FakeReq:
    def __init__(self, ret: dict[str, Any]) -> None:
        self._ret = ret

    def execute(self) -> dict[str, Any]:
        return self._ret


class _FakeValues:
    def __init__(self, calls: dict[str, Any]) -> None:
        self._calls = calls

    def update(self, **kwargs: Any) -> _FakeReq:
        self._calls["update"] = kwargs
        return _FakeReq({})


class _FakeSpreadsheets:
    def __init__(self, calls: dict[str, Any]) -> None:
        self._calls = calls

    def batchUpdate(self, **kwargs: Any) -> _FakeReq:  # noqa: N802 (google API method name)
        self._calls["batchUpdate"] = kwargs
        return _FakeReq({"replies": [{"addSheet": {"properties": {"sheetId": 99}}}]})

    def values(self) -> _FakeValues:
        return _FakeValues(self._calls)


class _FakeService:
    def __init__(self, calls: dict[str, Any]) -> None:
        self._calls = calls

    def spreadsheets(self) -> _FakeSpreadsheets:
        return _FakeSpreadsheets(self._calls)


class _FakeDiscovery:
    def __init__(self, calls: dict[str, Any]) -> None:
        self._calls = calls

    def build(self, _name: str, _version: str, **_kwargs: Any) -> _FakeService:
        return _FakeService(self._calls)


class _FakeCreds:
    @staticmethod
    def from_service_account_file(_path: str, **_kwargs: Any) -> object:
        return object()


class _FakeSa:
    Credentials = _FakeCreds


async def test_sheet_exporter_adds_tab_and_writes(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    creds = tmp_path / "sa.json"
    creds.write_text("{}")
    calls: dict[str, Any] = {}
    monkeypatch.setattr(se, "_discovery", _FakeDiscovery(calls))
    monkeypatch.setattr(se, "_sa", _FakeSa)

    result = await SheetExporter(credentials_path=creds, spreadsheet_id="WB1").export(
        [_output_row("a.gov"), _output_row("b.edu")], title="My Export"
    )

    assert result.spreadsheet_id == "WB1"
    assert result.tab == "My Export"
    assert result.url == "https://docs.google.com/spreadsheets/d/WB1/edit#gid=99"
    assert result.row_count == 2
    added = calls["batchUpdate"]["body"]["requests"][0]["addSheet"]["properties"]["title"]
    assert added == "My Export"  # a NEW tab, not the master Sheet1
    assert calls["update"]["range"] == "'My Export'!A1"
    values = calls["update"]["body"]["values"]
    assert values[0] == OUTPUT_HEADER
    assert len(values) == 3  # header + 2 rows
    assert values[1][0] == "a.gov"
