"""Population and Domain Rating must reach the sheet as NUMBERS, not text (ADR-035).

The writer sent every cell with valueInputOption="RAW", so Google stored "39287377" as a
string. Sorting a text column is lexicographic: Newport Beach's 83,845 sorts above
California's 39,287,377, and DR 9 sorts above DR 88. 46% of the delivered sheet sorted above
California. The client's first instinct with a 2,239-row sheet is to sort it.
"""

from authority_finder.output.models import OUTPUT_HEADER, OutputRow
from authority_finder.output.sheets_writer import to_sheet_values

ROW = OutputRow(
    website="pinellas.gov",
    specific_page="https://pinellas.gov/mental-health/",
    email="info@pinellas.gov",
    phone="+17274641000",
    contact_source="mailto (same-domain)",
    contact_trust="high",
    organization_description="County human services",
    geo_served="Florida",
    population=23_002_597,
    competitor_links="—",
    source_tag="MHD",
    date_added="2026-08-05",
    confidence="high",
    domain_rating=54.0,
)

POP = OUTPUT_HEADER.index("Population")
DR = OUTPUT_HEADER.index("Domain Rating")


class TestNumericColumns:
    def test_population_is_sent_as_a_number(self) -> None:
        cells = to_sheet_values([ROW])[0]
        assert cells[POP] == 23_002_597
        assert not isinstance(cells[POP], str)

    def test_domain_rating_is_sent_as_a_number(self) -> None:
        cells = to_sheet_values([ROW])[0]
        assert cells[DR] == 54
        assert not isinstance(cells[DR], str)

    def test_a_missing_value_stays_blank_not_zero(self) -> None:
        """Blank means 'not measured'. A 0 would claim no authority / no population."""
        row = ROW.model_copy(update={"population": None, "domain_rating": None})
        cells = to_sheet_values([row])[0]
        assert cells[POP] == ""
        assert cells[DR] == ""

    def test_every_other_column_is_still_text(self) -> None:
        cells = to_sheet_values([ROW])[0]
        for index, value in enumerate(cells):
            if index not in {POP, DR}:
                assert isinstance(value, str), OUTPUT_HEADER[index]

    def test_width_matches_the_header(self) -> None:
        assert len(to_sheet_values([ROW])[0]) == len(OUTPUT_HEADER)
