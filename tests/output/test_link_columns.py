"""The four new deliverable columns, appended after every shipped one (ADR-027/039).

Competitor Links is contractual — it means the brief's 16 and nothing else. The wider seed
lists therefore get their OWN columns rather than changing what a delivered column means.

The raw outbound-domain list is deliberately NOT a sheet column: it runs to hundreds of
domains per row and would be noise to the client. It is persisted anyway, so re-classifying
against a wider seed list later is a database pass, not another crawl.
"""

from authority_finder.output.models import OUTPUT_HEADER, OutputRow

_SHIPPED = [
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
    "Domain Rating",
    "Contact Found On",
]


def _row(**kwargs: object) -> OutputRow:
    base: dict[str, object] = {
        "website": "ucr.edu",
        "specific_page": "https://ucr.edu/resources",
        "email": "",
        "phone": "",
        "contact_source": "",
        "contact_trust": "low",
        "organization_description": "",
        "geo_served": "Riverside, California",
        "population": None,
        "competitor_links": "—",
        "source_tag": "MHD",
        "date_added": "2026-08-07",
        "confidence": "low",
    }
    return OutputRow(**(base | kwargs))  # pyright: ignore[reportArgumentType]


class TestColumnsAreAppendOnly:
    def test_every_shipped_column_keeps_its_index(self) -> None:
        assert OUTPUT_HEADER[: len(_SHIPPED)] == _SHIPPED

    def test_the_four_new_columns_come_after(self) -> None:
        assert OUTPUT_HEADER[len(_SHIPPED) :] == [
            "Addiction Directories",
            "Mental Health Directories",
            "Support Groups",
            "Support Groups Found On",
        ]

    def test_the_dedupe_key_columns_are_unmoved(self) -> None:
        """_existing_keys reads these positionally out of the live tab."""
        assert OUTPUT_HEADER.index("Website") == 0
        assert OUTPUT_HEADER.index("Geo Served") == 7

    def test_competitor_links_did_not_move_or_change_name(self) -> None:
        assert OUTPUT_HEADER.index("Competitor Links") == 9


class TestCells:
    def test_a_row_with_no_links_renders_the_blank_marker(self) -> None:
        cells = _row().cells()
        for column in ("Addiction Directories", "Mental Health Directories", "Support Groups"):
            assert cells[OUTPUT_HEADER.index(column)] == "—"

    def test_found_on_is_empty_not_dashed_when_there_is_nothing_to_show(self) -> None:
        """An empty provenance cell reads as 'not applicable'; a dash reads as a finding."""
        assert _row().cells()[OUTPUT_HEADER.index("Support Groups Found On")] == ""

    def test_domains_render_semicolon_joined(self) -> None:
        cells = _row(
            addiction_directories="drugrehab.com; rehabs.com",
            support_groups="aa.org; na.org",
            support_groups_found_on="https://ucr.edu/resources",
        ).cells()
        assert cells[OUTPUT_HEADER.index("Addiction Directories")] == "drugrehab.com; rehabs.com"
        assert cells[OUTPUT_HEADER.index("Support Groups")] == "aa.org; na.org"
        assert cells[OUTPUT_HEADER.index("Support Groups Found On")] == "https://ucr.edu/resources"

    def test_cells_length_still_matches_the_header(self) -> None:
        assert len(_row().cells()) == len(OUTPUT_HEADER)


class TestRawDomainsArePersistedButNotPublished:
    def test_the_field_exists_and_defaults_empty(self) -> None:
        assert _row().outbound_domains == ""

    def test_it_is_not_a_sheet_column(self) -> None:
        assert "outbound_domains" in OutputRow.SHEET_EXCLUDED_FIELDS
        assert len(_row().cells()) == len(OUTPUT_HEADER)

    def test_it_survives_on_the_row(self) -> None:
        row = _row(outbound_domains="aa.org; weather.gov; nami.org")
        assert row.outbound_domains == "aa.org; weather.gov; nami.org"
