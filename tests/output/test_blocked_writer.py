"""The blocked list is the deliverable that stops ncala.org vanishing."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import HttpUrl

from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.output.blocked_writer import BLOCKED_HEADER, collect_blocked, write_blocked
from authority_finder.page_detector.models import CandidateOutcome, DetectionResult

NOW = datetime(2026, 7, 31, tzinfo=UTC)
GEO = GeoRef(
    site_id="ah",
    url="https://addictionhotline.com/north-carolina/",
    level="state",
    state="north-carolina",
)


def _outcome(domain: str, status: str, reason: str | None) -> CandidateOutcome:
    return CandidateOutcome(
        candidate=CandidateSite(
            registrable_domain=domain,
            url=HttpUrl(f"https://{domain}/"),
            title=domain,
            snippet="",
            domain_class="other",
            geo=GEO,
            source_queries=[],
            discovered_at=NOW,
        ),
        status=status,  # pyright: ignore[reportArgumentType]
        block_reason=reason,
    )


def _result(outcomes: list[CandidateOutcome]) -> DetectionResult:
    return DetectionResult(geo=GEO, outcomes=outcomes)


class TestCollection:
    def test_the_ncala_case_is_surfaced(self) -> None:
        rows = collect_blocked([_result([_outcome("ncala.org", "fetch_failed", "captcha")])])
        assert [r.website for r in rows] == ["ncala.org"]
        assert rows[0].reason == "captcha"

    def test_a_hard_403_is_surfaced(self) -> None:
        rows = collect_blocked([_result([_outcome("x.org", "fetch_failed", "forbidden")])])
        assert len(rows) == 1

    def test_robots_is_not_surfaced(self) -> None:
        """We chose not to fetch it; that is not the site blocking us."""
        rows = collect_blocked([_result([_outcome("x.org", "fetch_failed", "robots")])])
        assert rows == []

    def test_unreachable_is_not_surfaced(self) -> None:
        """A 404 leaves nothing for a human to visit."""
        rows = collect_blocked([_result([_outcome("x.org", "fetch_failed", "unreachable")])])
        assert rows == []

    def test_successful_detections_are_not_surfaced(self) -> None:
        rows = collect_blocked([_result([_outcome("ok.org", "detected", None)])])
        assert rows == []

    def test_deduped_by_domain_and_geo(self) -> None:
        o = _outcome("ncala.org", "fetch_failed", "captcha")
        rows = collect_blocked([_result([o, o])])
        assert len(rows) == 1


class TestWriter:
    def test_writes_header_and_rows(self, tmp_path: Path) -> None:
        rows = collect_blocked([_result([_outcome("ncala.org", "fetch_failed", "captcha")])])
        target = tmp_path / "blocked.csv"
        assert write_blocked(rows, target) == 1
        lines = target.read_text().splitlines()
        assert lines[0] == ",".join(BLOCKED_HEADER)
        assert "ncala.org" in lines[1]
        assert "captcha" in lines[1]

    def test_empty_run_still_writes_a_header(self, tmp_path: Path) -> None:
        target = tmp_path / "blocked.csv"
        assert write_blocked([], target) == 0
        assert target.read_text().strip() == ",".join(BLOCKED_HEADER)
