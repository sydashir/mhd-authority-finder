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


def _orow(
    domain: str, *, trust: str = "high", pop: int | None = 100, geo: str = "Maryland"
) -> OutputRow:
    """An OutputRow with explicit contact_trust/population/geo for sort assertions."""
    return OutputRow(
        website=domain,
        specific_page=f"https://{domain}/p",
        email="",
        phone="",
        contact_source="",
        contact_trust=trust,
        organization_description="",
        geo_served=geo,
        population=pop,
        competitor_links="—",
        source_tag="MHD",
        date_added="2026-06-19",
        confidence="high",
    )


def test_dedupe_keeps_one_per_domain_geo() -> None:
    rows = [_row("a.gov"), _row("a.gov"), _row("b.gov")]
    out = dedupe_and_sort(rows)
    assert len(out) == 2
    assert {r.website for r in out} == {"a.gov", "b.gov"}


def test_sort_trust_then_population() -> None:
    rows = [
        _orow("low.gov", trust="low", pop=900),
        _orow("high-small.gov", trust="high", pop=10),
        _orow("high-big.gov", trust="high", pop=999),
    ]
    out = dedupe_and_sort(rows)
    # contact trust first; within a trust band, bigger population first
    assert [r.website for r in out] == ["high-big.gov", "high-small.gov", "low.gov"]


def test_trust_outranks_geo() -> None:
    # A high-trust row in a late-alphabet geo must still beat a low-trust row in an
    # early-alphabet geo — the whole point of the S24 re-sort (trust before geo).
    rows = [
        _orow("low-early.gov", trust="low", geo="Alabama", pop=999),
        _orow("high-late.gov", trust="high", geo="Wyoming", pop=1),
    ]
    out = dedupe_and_sort(rows)
    assert [r.website for r in out] == ["high-late.gov", "low-early.gov"]


def test_unknown_population_sorts_last_within_trust() -> None:
    rows = [
        _orow("known.gov", trust="high", pop=5),
        _orow("unknown.gov", trust="high", pop=None),
    ]
    out = dedupe_and_sort(rows)
    assert [r.website for r in out] == ["known.gov", "unknown.gov"]


def test_population_then_geo_within_trust() -> None:
    # equal trust + equal population → stable geo (alphabetical) tiebreak
    rows = [
        _orow("b.gov", trust="high", pop=100, geo="Nevada"),
        _orow("a.gov", trust="high", pop=100, geo="Georgia"),
    ]
    out = dedupe_and_sort(rows)
    assert [r.geo_served for r in out] == ["Georgia", "Nevada"]


def test_write_csv_header_and_count(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    n = write_csv([_row("a.gov"), _row("b.gov"), _row("a.gov")], path)
    assert n == 2
    with path.open(encoding="utf-8") as handle:
        reader = list(csv.reader(handle))
    assert reader[0] == OUTPUT_HEADER
    assert len(reader) == 3  # header + 2 deduped rows
