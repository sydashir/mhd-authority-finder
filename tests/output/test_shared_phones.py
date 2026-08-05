"""A phone on organisations in 2+ states is a shared line, not anyone's own number (ADR-035).

The curated hotline blocklist in contact_extractor is necessary but not sufficient: it is
hand-written, and the S48 audit proved it had drifted — it held 3 numbers while 10 were live
in the deliverable. My own first check reported ZERO hotlines because I only tested the three
I knew about.

This is the data-driven half. It needs no list: mined from the delivered sheet, +18009898137
appeared on SEVEN different organisations across SEVEN states (carealabama.net, carearizona.org,
caredelaware.org, caremichigan.org, caremissouri.org …). No curated list would have caught it.

Deliberately keyed on STATE, not row count: two agencies in one state genuinely do share a
switchboard (dss.sd.gov and sdbehavioralhealth.gov, health.maryland.gov and
stopoverdose.maryland.gov), and blanking those would destroy real contacts.
"""

from authority_finder.output.models import OutputRow
from authority_finder.output.shared_phones import blank_shared_phones


def _row(website: str, geo: str, phone: str) -> OutputRow:
    return OutputRow(
        website=website,
        specific_page=f"https://{website}/",
        email="",
        phone=phone,
        contact_source="",
        contact_trust="low",
        organization_description="",
        geo_served=geo,
        population=None,
        competitor_links="—",
        source_tag="MHD",
        date_added="2026-08-05",
        confidence="low",
    )


class TestCrossStateSharing:
    def test_a_line_shared_across_states_is_blanked(self) -> None:
        """The real case: one number, seven 'care{state}' sites, seven states."""
        rows = [
            _row("carealabama.net", "Alabama", "+18009898137"),
            _row("carearizona.org", "Arizona", "+18009898137"),
            _row("caredelaware.org", "Delaware", "+18009898137"),
        ]
        cleaned, blanked = blank_shared_phones(rows)
        assert blanked == 3
        assert all(r.phone == "" for r in cleaned)

    def test_two_agencies_in_one_state_keep_their_switchboard(self) -> None:
        """South Dakota's DSS and Behavioral Health really do share a line."""
        rows = [
            _row("dss.sd.gov", "South Dakota", "+16053675236"),
            _row("sdbehavioralhealth.gov", "South Dakota", "+16053675236"),
        ]
        cleaned, blanked = blank_shared_phones(rows)
        assert blanked == 0
        assert all(r.phone == "+16053675236" for r in cleaned)

    def test_sub_state_geos_resolve_to_their_state(self) -> None:
        """'Orange County, California' and 'California' are the SAME state, not two."""
        rows = [
            _row("oc.gov", "Orange County, California", "+18558865400"),
            _row("ocgov.com", "California", "+18558865400"),
        ]
        _, blanked = blank_shared_phones(rows)
        assert blanked == 0

    def test_the_same_organisation_across_geos_is_not_penalised(self) -> None:
        """One org legitimately serves many geos — that is not a shared hotline."""
        rows = [
            _row("mhanational.org", "Kentucky", "+15551234567"),
            _row("mhanational.org", "Louisiana", "+15551234567"),
        ]
        _, blanked = blank_shared_phones(rows)
        assert blanked == 0

    def test_rows_without_a_phone_are_untouched(self) -> None:
        rows = [_row("a.gov", "Ohio", ""), _row("b.gov", "Iowa", "")]
        cleaned, blanked = blank_shared_phones(rows)
        assert blanked == 0
        assert all(r.phone == "" for r in cleaned)

    def test_nothing_else_on_the_row_changes(self) -> None:
        rows = [
            _row("carealabama.net", "Alabama", "+18009898137"),
            _row("carearizona.org", "Arizona", "+18009898137"),
        ]
        cleaned, _ = blank_shared_phones(rows)
        assert cleaned[0].website == "carealabama.net"
        assert cleaned[0].geo_served == "Alabama"
        assert cleaned[0].competitor_links == "—"
