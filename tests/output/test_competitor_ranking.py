"""An org that already lists a competing directory has PROVEN it will list one (ADR-011).

That is a stronger buying signal than any contact-trust band or Domain Rating: it is
demonstrated behaviour rather than an inferred property. So it sorts first.
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


class TestCompetitorLinkRanksFirst:
    def test_a_linking_org_outranks_a_higher_trust_non_linking_org(self) -> None:
        """This is the whole point: proven behaviour beats a better contact grade."""
        rows = dedupe_and_sort(
            [
                _row("high-trust-no-links.org", trust="high"),
                _row("low-trust-but-links.org", trust="low", competitors="rehabs.com"),
            ]
        )
        assert rows[0].website == "low-trust-but-links.org"

    def test_multiple_linking_orgs_keep_trust_order_among_themselves(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("links-low.org", trust="low", competitors="rehabs.com"),
                _row("links-high.org", trust="high", competitors="recovery.com"),
            ]
        )
        assert [r.website for r in rows] == ["links-high.org", "links-low.org"]

    def test_the_em_dash_placeholder_is_not_treated_as_a_link(self) -> None:
        """'—' is how 'no competitor links' is written; it must not rank as proof."""
        rows = dedupe_and_sort(
            [
                _row("no-links.org", trust="high", competitors="—"),
                _row("links.org", trust="low", competitors="samhsa.gov"),
            ]
        )
        assert rows[0].website == "links.org"

    def test_an_empty_string_is_not_treated_as_a_link(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("empty.org", trust="high", competitors=""),
                _row("links.org", trust="low", competitors="rehabs.com"),
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

    def test_dedupe_keeps_the_linking_row_when_a_domain_appears_twice(self) -> None:
        rows = dedupe_and_sort(
            [
                _row("dup.org", trust="high", competitors="—"),
                _row("dup.org", trust="low", competitors="rehabs.com"),
            ]
        )
        assert len(rows) == 1
        assert rows[0].competitor_links == "rehabs.com"
