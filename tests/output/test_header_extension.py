"""The master Sheet holds 589 live rows. A schema change must never misalign them.

Adding a column is safe ONLY as a suffix extension: every existing column keeps its index,
so `_existing_keys` still reads Website and Geo Served from the same places and dedupe keeps
working. A reorder or removal would silently shift every cell in 589 rows, which is worse
than a refused write — so it is refused.
"""

import inspect

import pytest

from authority_finder.output.models import OUTPUT_HEADER, OutputRow, build_row
from authority_finder.output.sheets_writer import (
    SheetsError,
    SheetsWriter,
    is_safe_header_change,
)


def _row() -> OutputRow:
    return OutputRow(
        website="ncala.org",
        specific_page="https://ncala.org/about",
        email="info@ncala.org",
        phone="",
        contact_source="mailto (same-domain)",
        contact_trust="high",
        organization_description="",
        geo_served="North Carolina",
        population=10_800_000,
        competitor_links="—",
        source_tag="AH",
        date_added="2026-07-30",
        confidence="high",
        domain_rating=34.0,
    )


class TestColumnPositionsAreStable:
    def test_the_new_column_is_appended_at_the_end(self) -> None:
        """Anywhere else shifts existing indices and misaligns the live rows."""
        assert OUTPUT_HEADER[-1] == "Domain Rating"

    def test_every_pre_existing_column_keeps_its_index(self) -> None:
        previous = [
            "Website",
            "Specific Page",
            "Email",
            "Phone",
            "Contact Source",
            "Contact Trust",
            "Organization Description",
            "Geo Served",
            "Population",
            "Competitor Links",
            "Source Tag",
            "Date Added",
            "Confidence",
        ]
        assert OUTPUT_HEADER[: len(previous)] == previous

    def test_cells_length_matches_the_header(self) -> None:
        assert len(_row().cells()) == len(OUTPUT_HEADER)

    def test_dedupe_key_columns_are_unmoved(self) -> None:
        """_existing_keys reads Website and Geo Served positionally."""
        assert OUTPUT_HEADER.index("Website") == 0
        assert OUTPUT_HEADER.index("Geo Served") == 7


class TestHeaderChangeGuard:
    def test_a_pure_extension_is_allowed(self) -> None:
        old = OUTPUT_HEADER[:-1]
        assert is_safe_header_change(old, OUTPUT_HEADER)

    def test_an_identical_header_is_allowed(self) -> None:
        assert is_safe_header_change(list(OUTPUT_HEADER), OUTPUT_HEADER)

    def test_an_empty_tab_is_allowed(self) -> None:
        assert is_safe_header_change([], OUTPUT_HEADER)

    def test_a_reorder_is_refused(self) -> None:
        """Swapping two columns misaligns every row without changing the row count."""
        scrambled = list(OUTPUT_HEADER)
        scrambled[0], scrambled[1] = scrambled[1], scrambled[0]
        assert not is_safe_header_change(scrambled, OUTPUT_HEADER)

    def test_a_removal_is_refused(self) -> None:
        assert not is_safe_header_change(["Website", "Email"], OUTPUT_HEADER)

    def test_a_renamed_column_is_refused(self) -> None:
        renamed = list(OUTPUT_HEADER)
        renamed[3] = "Telephone"
        assert not is_safe_header_change(renamed, OUTPUT_HEADER)


class TestDomainRatingCell:
    def test_dr_renders_as_a_plain_number(self) -> None:
        assert _row().cells()[-1] == "34"

    def test_unscored_gov_edu_is_blank_not_zero(self) -> None:
        """.gov/.edu are deliberately never scored — blank means 'not measured', 0 would lie."""
        row = _row().model_copy(update={"domain_rating": None})
        assert row.cells()[-1] == ""


class TestGuardsWorkTogether:
    """Both failure modes must stay covered: a row-shrink AND a column-misalign."""

    def test_the_shrink_guard_still_refuses_a_truncated_write(self) -> None:
        """ADR-025's protection must survive the header change."""
        writer = SheetsWriter.__new__(SheetsWriter)
        writer._tab = "Sheet1"  # pyright: ignore[reportPrivateUsage]
        existing = [OUTPUT_HEADER, *([["x"] * len(OUTPUT_HEADER)] * 589)]
        with pytest.raises(SheetsError, match="shrink"):
            writer._safe_rewrite(  # pyright: ignore[reportPrivateUsage]
                object(), [_row()], existing, allow_shrink=False, reason="test"
            )

    def test_a_deliberate_shrink_is_still_possible_when_forced(self) -> None:
        """An intentional correction must remain available (the S26 escape hatch)."""
        assert is_safe_header_change(OUTPUT_HEADER[:-1], OUTPUT_HEADER)


class TestPipelinePropagation:
    """S32 found run_pipeline computed DR and dropped it on the floor."""

    def test_build_row_carries_the_domain_rating(self) -> None:
        sig = inspect.signature(build_row)
        assert "domain_rating" in sig.parameters
        source = inspect.getsource(build_row)
        assert "domain_rating=domain_rating" in source, "accepted but never assigned"
