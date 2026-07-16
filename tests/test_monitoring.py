"""Error monitoring (ADR-023): scrubbing policy, DSN-gating (silent in dev), and the
background-run capture (the 3am scheduled-run case). No real events are ever sent."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
import sentry_sdk

from authority_finder.monitoring import init_sentry, scrub_event
from backend import jobs


def test_scrub_strips_cookies_body_and_sensitive_headers() -> None:
    event: dict[str, Any] = {
        "request": {
            "cookies": {"session": "SECRET-JWT"},
            "data": {"password": "hunter2"},
            "headers": {"Cookie": "session=abc", "Authorization": "Bearer xyz", "Accept": "json"},
        }
    }
    scrubbed = scrub_event(event, {})
    assert "cookies" not in scrubbed["request"]
    assert "data" not in scrubbed["request"]
    assert scrubbed["request"]["headers"]["Cookie"] == "[scrubbed]"
    assert scrubbed["request"]["headers"]["Authorization"] == "[scrubbed]"
    assert scrubbed["request"]["headers"]["Accept"] == "json"  # non-sensitive header kept


def test_scrub_redacts_emails_in_exception_and_message() -> None:
    event: dict[str, Any] = {
        "message": "failed to reach bh@ochealthinfo.gov",
        "exception": {"values": [{"value": "bounced: director@county.gov is invalid"}]},
    }
    scrubbed = scrub_event(event, {})
    assert "bh@ochealthinfo.gov" not in scrubbed["message"]
    assert "[email]" in scrubbed["message"]
    assert "director@county.gov" not in scrubbed["exception"]["values"][0]["value"]
    assert "[email]" in scrubbed["exception"]["values"][0]["value"]


def test_scrub_is_safe_on_a_minimal_event() -> None:
    assert scrub_event({}, {}) == {}


def test_monitoring_disabled_without_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_init(**_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    # No DSN → returns False and never touches Sentry (silent in dev + tests).
    assert init_sentry(dsn="", environment="production") is False
    assert called is False


def test_monitoring_enabled_with_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_init(**kwargs: object) -> None:
        seen.update(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    assert init_sentry(dsn="https://k@example.ingest.sentry.io/1", environment="staging") is True
    assert seen["environment"] == "staging"
    assert seen["send_default_pii"] is False  # the scrubbing default we rely on
    assert seen["before_send"] is scrub_event


async def test_execute_run_captures_a_background_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[BaseException] = []

    def fake_capture(exc: BaseException) -> None:
        captured.append(exc)

    monkeypatch.setattr(sentry_sdk, "capture_exception", fake_capture)
    monkeypatch.setattr(jobs, "finish_run", AsyncMock())  # skip the DB write

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_a: object) -> bool:
            return False

        async def commit(self) -> None:
            return None

    async def failing_job(_run_id: int, _site: str, _mode: str) -> jobs.RunSummary:
        raise RuntimeError("pipeline died mid-run at 3am")

    # FakeSession (the class) is the sessionmaker — execute_run calls it to open a session.
    await jobs.execute_run(FakeSession, 7, failing_job, site="both", mode="incremental")  # type: ignore[arg-type]

    assert len(captured) == 1
    assert isinstance(captured[0], RuntimeError)
    assert "3am" in str(captured[0])
