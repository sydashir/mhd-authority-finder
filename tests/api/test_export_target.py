"""The UI's export must never drop tabs into the client's own workbook (ADR-035).

EXPORT_SHEET_ID fell back to GOOGLE_SHEET_ID, so every "Export to Google Sheet" click added a
tab to the file the client opens. Two such tabs (622 rows each, a superseded schema) were
sitting beside the deliverable when it went out for review, with nothing saying which was
current. Falling back to the client's file is worse than refusing.
"""

import pytest
from fastapi import HTTPException

from backend.routers.export import resolve_export_target


class TestExportTarget:
    def test_a_dedicated_workbook_is_used(self) -> None:
        assert resolve_export_target(export_id="EXPORTS", master_id="MASTER") == "EXPORTS"

    def test_an_unset_export_id_refuses_rather_than_using_the_master(self) -> None:
        with pytest.raises(HTTPException) as exc:
            resolve_export_target(export_id="", master_id="MASTER")
        assert exc.value.status_code == 503
        assert "EXPORT_SHEET_ID" in exc.value.detail

    def test_pointing_it_at_the_master_is_also_refused(self) -> None:
        """Setting them equal is the same mistake spelled differently."""
        with pytest.raises(HTTPException) as exc:
            resolve_export_target(export_id="MASTER", master_id="MASTER")
        assert exc.value.status_code == 503

    def test_whitespace_is_not_a_configured_value(self) -> None:
        with pytest.raises(HTTPException):
            resolve_export_target(export_id="   ", master_id="MASTER")
