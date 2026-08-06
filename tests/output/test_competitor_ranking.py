"""An org that already lists a competing directory has PROVEN it will list one (ADR-011).

That is a strong buying signal — demonstrated behaviour rather than an inferred property — so
it ranks rows WITHIN a contact-trust band. It no longer sorts ahead of trust: doing so put a
medium-trust row above a high-trust one and made the Trust column read as unsorted, which the
client reported (ADR-038). Trust says whether the email is safe to send; that has to lead.
"""

from authority_finder.output.csv_writer import dedupe_and_sort
from authority_finder.output.models import OutputRow


def _row(
    website: str,
    *,
    trust: str = "low",
    competitors: str = "—",
    pop: int | None = None,
    geo: str = "Texas",
) -> OutputRow:
    return OutputRow(
        website=website,
        specific_page=f"https://{website}/x",
        email="a@b.org",
        phone="",
        contact_source="mailto (same-domain)",
        contact_trust=trust,
        organization_description="",
        geo_served=geo,
        population=pop,
        competitor_links=competitors,
        source_tag="AH",
        date_added="2026-07-30",
        confidence=trust,
    )


class TestCompetitorLinkRanksWithinATrustBand:
    def test_trust_outranks_a_competitor_link(self) -> None:
        """Superseded by ADR-038 — this pair used to come back the other way round."""
        rows = dedupe_and_sort(
            [
                _row("high-trust-no-links.org", trust="high"),
                _row("low-trust-but-links.org", trust="low", competitors="rehabs.com"),
            ]
        )
        assert rows[0].website == "high-trust-no-links.org"

    def test_multiple_linking_orgs_keep_trust_order_among_themselves(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("links-low.org", trust="low", competitors="rehabs.com"),
                _row("links-high.org", trust="high", competitors="recovery.com"),
            ]
        )
        assert [r.website for r in rows] == ["links-high.org", "links-low.org"]

    def test_the_em_dash_placeholder_is_not_treated_as_a_link(self) -> None:
        """'—' is how 'no competitor links' is written; it must not rank as proof.

        Compared within ONE band, so the assertion tests the link rule and not trust.
        """
        rows = dedupe_and_sort(
            [
                _row("no-links.org", trust="high", competitors="—"),
                _row("links.org", trust="high", competitors="samhsa.gov"),
            ]
        )
        assert rows[0].website == "links.org"

    def test_an_empty_string_is_not_treated_as_a_link(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("empty.org", trust="high", competitors=""),
                _row("links.org", trust="high", competitors="rehabs.com"),
            ]
        )
        assert rows[0].website == "links.org"

    def test_trust_then_population_still_orders_the_non_linking_rows(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("small.org", trust="high", pop=1000),
                _row("big.org", trust="high", pop=900000),
                _row("medium-trust.org", trust="medium", pop=999999),
            ]
        )
        assert [r.website for r in rows] == ["big.org", "small.org", "medium-trust.org"]

    def test_dedupe_keeps_the_linking_row_within_the_same_trust_band(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("dup.org", trust="high", competitors="—"),
                _row("dup.org", trust="high", competitors="rehabs.com"),
            ]
        )
        assert len(rows) == 1
        assert rows[0].competitor_links == "rehabs.com"

    def test_dedupe_keeps_the_higher_trust_row_when_the_bands_differ(self) -> None:
        """Dedupe follows the sort, so the surviving row is now the better CONTACT.

        The link is a property of the org, which is unchanged either way; the contact grade
        is what the rep acts on, so keeping the high-trust row loses less.
        """
        rows = dedupe_and_sort(
            [
                _row("dup.org", trust="high", competitors="—"),
                _row("dup.org", trust="low", competitors="rehabs.com"),
            ]
        )
        assert len(rows) == 1
        assert rows[0].contact_trust == "high"
