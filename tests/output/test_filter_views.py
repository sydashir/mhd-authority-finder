"""Saved filter views for the MHD / AH split (ADR-042).

The feasibility doc promised separate MHD and AH tabs. Measured on live sitemaps, AH publishes
56 geographies and MHD 6,299, of which 54 overlap — so an AH tab would be a strict subset of
the MHD tab and 1,965 organisations would appear on both. Filter views give the same two
views with no duplicated rows and no second outreach surface.

The criteria are expressed as "hide the other site's exclusive tag" rather than "show these",
which is what keeps a view correct when the data shifts: an AH-only row appearing tomorrow
shows up in the AH view without anyone editing the filter.
"""

from authority_finder.output.filter_views import FILTER_VIEWS, build_filter_view_specs
from authority_finder.output.models import OUTPUT_HEADER

SHEET_ID = 1234


def _specs(row_count: int = 2237) -> list[dict[str, object]]:
    return build_filter_view_specs(sheet_id=SHEET_ID, row_count=row_count)


def _by_title(row_count: int = 2237) -> dict[str, dict[str, object]]:
    return {str(s["title"]): s for s in _specs(row_count)}


class TestTheTwoViews:
    def test_both_views_are_defined(self) -> None:
        assert set(_by_title()) == {"MHD prospects", "AH prospects"}

    def test_the_titles_are_stable(self) -> None:
        """A renamed view is a NEW view to Sheets, so the old one would linger."""
        assert [v.title for v in FILTER_VIEWS] == ["MHD prospects", "AH prospects"]


class TestCriteriaHideTheOtherSitesExclusiveTag:
    """Hiding is future-proof; an explicit allow-list would silently drop a new tag value."""

    def test_the_mhd_view_hides_only_ah(self) -> None:
        criteria = _by_title()["MHD prospects"]["criteria"]
        assert isinstance(criteria, dict)
        index = str(OUTPUT_HEADER.index("Source Tag"))
        assert criteria[index] == {"hiddenValues": ["AH"]}

    def test_the_ah_view_hides_only_mhd(self) -> None:
        criteria = _by_title()["AH prospects"]["criteria"]
        assert isinstance(criteria, dict)
        index = str(OUTPUT_HEADER.index("Source Tag"))
        assert criteria[index] == {"hiddenValues": ["MHD"]}

    def test_both_views_keep_the_both_rows(self) -> None:
        """94% of rows are 'Both' and belong in BOTH views — that is the whole point."""
        for spec in _specs():
            criteria = spec["criteria"]
            assert isinstance(criteria, dict)
            for rule in criteria.values():
                assert "Both" not in rule["hiddenValues"]


class TestTheRange:
    def test_it_is_derived_from_the_header_not_hard_coded(self) -> None:
        """A literal column count truncates the view the moment a column is added — the same
        defect that made _RANGE stop covering the sheet when Domain Rating shipped."""
        for spec in _specs():
            grid = spec["range"]
            assert isinstance(grid, dict)
            assert grid["endColumnIndex"] == len(OUTPUT_HEADER)

    def test_it_covers_the_header_row_and_every_data_row(self) -> None:
        grid = _specs(row_count=2237)[0]["range"]
        assert isinstance(grid, dict)
        assert grid["startRowIndex"] == 0  # the header, so the view is filterable by name
        assert grid["endRowIndex"] == 2238  # 1 header + 2237 data rows
        assert grid["startColumnIndex"] == 0
        assert grid["sheetId"] == SHEET_ID

    def test_the_range_tracks_the_row_count(self) -> None:
        grid = _specs(row_count=10)[0]["range"]
        assert isinstance(grid, dict)
        assert grid["endRowIndex"] == 11
