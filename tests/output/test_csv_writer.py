"""CSV writer: dedupe, value-ordered sort, header."""

import csv
from datetime import UTC, datetime
from pathlib import Path

from authority_finder.output.csv_writer import dedupe_and_sort, write_csv
from authority_finder.output.models import OUTPUT_HEADER, OutputRow, build_row
from authority_finder.page_detector.models import Confidence
from authority_finder.population.models import PopulationResult
from tests.output.conftest import geo_ref, outcome

NOW = datetime(2026, 6, 19, tzinfo=UTC)


def _pop(value: int | None) -> PopulationResult:
    return PopulationResult(
        value=value, matched_name=None, geo_level_used=None, confidence="exact", source_dataset="x"
    )


def _row(
    domain: str, *, confidence: Confidence = "high", pop: int | None = 100, level: str = "county"
) -> OutputRow:
    o = outcome(
        domain=domain, page_url=f"https://{domain}/p", confidence=confidence, geo=geo_ref(level)
    )
    return build_row(o, population=_pop(pop), now=NOW)


def test_dedupe_keeps_one_per_domain_geo() -> None:
    rows = [_row("a.gov"), _row("a.gov"), _row("b.gov")]
    out = dedupe_and_sort(rows)
    assert len(out) == 2
    assert {r.website for r in out} == {"a.gov", "b.gov"}


def test_sort_confidence_then_population() -> None:
    rows = [
        _row("low.gov", confidence="low", pop=900),
        _row("high-small.gov", confidence="high", pop=10),
        _row("high-big.gov", confidence="high", pop=999),
    ]
    out = dedupe_and_sort(rows)
    # same geo: high before low; within high, bigger population first
    assert [r.website for r in out] == ["high-big.gov", "high-small.gov", "low.gov"]


def test_unknown_population_sorts_last_within_confidence() -> None:
    rows = [
        _row("known.gov", confidence="high", pop=5),
        _row("unknown.gov", confidence="high", pop=None),
    ]
    out = dedupe_and_sort(rows)
    assert [r.website for r in out] == ["known.gov", "unknown.gov"]


def test_write_csv_header_and_count(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    n = write_csv([_row("a.gov"), _row("b.gov"), _row("a.gov")], path)
    assert n == 2
    with path.open(encoding="utf-8") as handle:
        reader = list(csv.reader(handle))
    assert reader[0] == OUTPUT_HEADER
    assert len(reader) == 3  # header + 2 deduped rows
