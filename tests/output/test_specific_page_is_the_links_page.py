"""Specific Page must be the page the client should OPEN (ADR-036).

The client reported a row whose Competitor Links did not appear on its Specific Page. We
answered by keeping the contact page in Specific Page and adding a 15th column naming the
real page. From his seat nothing changed: he clicks Specific Page, sees no competitor links,
and concludes we ignored him.

The column he clicks has to be the page with the links. The contact page moves to its own
column, because that is where the email and phone actually came from and it is still needed
for outreach — but it is the secondary fact, not the headline.
"""

from datetime import UTC, datetime

from authority_finder.output.models import OUTPUT_HEADER, OutputRow, choose_pages

NOW = datetime(2026, 8, 5, tzinfo=UTC)

CONTACT = "https://counseling.ucr.edu/"
LINKS = (
    "https://counseling.ucr.edu/resources-support-specialty-care-self-help-and-making-connections"
)


class TestChoosePages:
    def test_links_page_becomes_specific_page(self) -> None:
        """The ucr.edu case: the client opens Specific Page and sees the links."""
        specific, contact_on = choose_pages(detected_page=CONTACT, link_pages=[LINKS])
        assert specific == LINKS
        assert contact_on == CONTACT

    def test_no_swap_when_the_links_are_already_on_the_detected_page(self) -> None:
        specific, contact_on = choose_pages(detected_page=CONTACT, link_pages=[CONTACT])
        assert specific == CONTACT
        assert contact_on == "", "nothing to explain — one page did both jobs"

    def test_no_swap_when_there_are_no_competitor_links(self) -> None:
        specific, contact_on = choose_pages(detected_page=CONTACT, link_pages=[])
        assert specific == CONTACT
        assert contact_on == ""

    def test_the_first_link_page_wins_when_several_carry_links(self) -> None:
        other = "https://counseling.ucr.edu/other"
        specific, contact_on = choose_pages(detected_page=CONTACT, link_pages=[LINKS, other])
        assert specific == LINKS
        assert contact_on == CONTACT


class TestSchema:
    def test_the_column_is_named_for_what_it_holds(self) -> None:
        assert "Contact Found On" in OUTPUT_HEADER
        assert "Competitor Links Found On" not in OUTPUT_HEADER

    def test_specific_page_is_still_the_second_column(self) -> None:
        """It is the column the client clicks; it does not move."""
        assert OUTPUT_HEADER[1] == "Specific Page"

    def test_cells_still_match_the_header(self) -> None:
        row = OutputRow(
            website="ucr.edu",
            specific_page=LINKS,
            email="counseling@ucr.edu",
            phone="",
            contact_source="mailto (same-domain)",
            contact_trust="high",
            organization_description="",
            geo_served="California",
            population=None,
            competitor_links="samhsa.gov",
            source_tag="MHD",
            date_added="2026-08-05",
            confidence="medium",
            contact_found_on=CONTACT,
        )
        cells = row.cells()
        assert len(cells) == len(OUTPUT_HEADER)
        assert cells[OUTPUT_HEADER.index("Specific Page")] == LINKS
        assert cells[OUTPUT_HEADER.index("Contact Found On")] == CONTACT
