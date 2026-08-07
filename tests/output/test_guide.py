"""The legend must never drift from the columns it describes (ADR-041).

It drifted once already: written by a one-off script, then hand-maintained, so it documented
15 columns while the sheet shipped 19. The client was told nothing about the four newest —
including the one whose relationship to Competitor Links caused the confusion.
"""

from authority_finder.output.guide import COLUMN_GUIDE, build_guide_rows
from authority_finder.output.models import OUTPUT_HEADER


class TestEveryColumnIsDocumented:
    def test_no_column_is_missing_an_entry(self) -> None:
        missing = [c for c in OUTPUT_HEADER if c not in COLUMN_GUIDE]
        assert not missing, f"undocumented columns would ship unexplained: {missing}"

    def test_no_entry_describes_a_column_that_does_not_exist(self) -> None:
        stale = [c for c in COLUMN_GUIDE if c not in OUTPUT_HEADER]
        assert not stale, f"the legend describes columns the sheet no longer has: {stale}"

    def test_the_rows_follow_header_order(self) -> None:
        rows = build_guide_rows()
        described = [r[0] for r in rows if r[0] in COLUMN_GUIDE]
        assert described == OUTPUT_HEADER

    def test_every_entry_says_something(self) -> None:
        for column, (meaning, blank) in COLUMN_GUIDE.items():
            assert len(meaning) > 20, column
            assert blank, column


class TestTheSubsetRelationshipIsExplained:
    """The client's actual complaint was that the split looked arbitrary."""

    def test_competitor_links_is_described_as_a_subset(self) -> None:
        meaning = COLUMN_GUIDE["Competitor Links"][0]
        assert "SUBSET" in meaning
        assert "Addiction Directories" in meaning

    def test_addiction_directories_is_described_as_the_full_list(self) -> None:
        assert "FULL LIST" in COLUMN_GUIDE["Addiction Directories"][0]

    def test_all_three_categories_are_described_as_full_lists(self) -> None:
        for column in ("Addiction Directories", "Mental Health Directories", "Support Groups"):
            assert "FULL LIST" in COLUMN_GUIDE[column][0], column

    def test_the_relationship_gets_its_own_note(self) -> None:
        text = " ".join(cell for row in build_guide_rows() for cell in row)
        assert "HOW THE LINK COLUMNS RELATE" in text
        assert "ALWAYS also appear in Addiction Directories" in text

    def test_the_grid_is_rectangular(self) -> None:
        assert {len(r) for r in build_guide_rows()} == {3}
