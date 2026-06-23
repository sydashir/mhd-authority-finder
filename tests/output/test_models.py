"""Output row assembly — full data and with holes."""

from datetime import UTC, datetime

from authority_finder.output.models import OUTPUT_HEADER, build_row, geo_served_label
from authority_finder.population.models import PopulationResult
from tests.output.conftest import geo_ref, outcome

NOW = datetime(2026, 6, 19, tzinfo=UTC)


def _pop(value: int | None, confidence: str = "exact") -> PopulationResult:
    return PopulationResult(
        value=value,
        matched_name="Orange County, California" if value else None,
        geo_level_used="county" if value else None,
        confidence=confidence,  # type: ignore[arg-type]
        source_dataset="ACS 5-year 2024",
    )


def test_full_row_assembly() -> None:
    row = build_row(outcome(), population=_pop(3170345), now=NOW)
    cells = row.cells()
    assert len(cells) == len(OUTPUT_HEADER)
    assert row.website == "ochealthinfo.gov"
    assert row.email == "bh@ochealthinfo.gov"
    assert row.phone == "+17148341234"
    assert row.geo_served == "Orange County, California"
    assert row.population == 3170345
    assert row.competitor_links == "—"
    assert row.source_tag == "MHD"
    assert row.date_added == "2026-06-19"
    assert row.confidence == "high"


def test_row_with_holes_blanks_not_crash() -> None:
    o = outcome(email=None, phone=None, confidence="low", snippet="")
    row = build_row(o, population=_pop(None, "not_found"), now=NOW)
    assert row.email == ""
    assert row.phone == ""
    assert row.population is None
    assert row.cells()[6] == ""  # Population cell blank, not "None"
    assert row.confidence == "low"


def test_source_tag_ah() -> None:
    o = outcome(geo=geo_ref("state", site_id="ah"))
    row = build_row(o, population=_pop(39538223), now=NOW)
    assert row.source_tag == "AH"
    assert row.geo_served == "California"


def test_geo_served_labels() -> None:
    assert geo_served_label(level="state", state="maryland", county=None, city=None) == "Maryland"
    assert (
        geo_served_label(level="county", state="california", county="orange-county", city=None)
        == "Orange County, California"
    )
    assert (
        geo_served_label(
            level="city", state="california", county="orange-county", city="newport-beach"
        )
        == "Newport Beach, California"
    )


def test_description_truncated() -> None:
    o = outcome(snippet="x" * 500)
    row = build_row(o, population=_pop(None), now=NOW)
    assert len(row.organization_description) <= 240
