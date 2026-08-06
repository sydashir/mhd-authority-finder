"""Trust leads the deliverable, then proven directory-listing behaviour (ADR-038).

The old order put competitor-linked rows first, so a MEDIUM-trust row with a link outranked
a HIGH-trust row without one. Opening the sheet, the Contact Trust column then reads
high, medium, low, high, medium, low — which looks unsorted, and the client said so.

Trust is the column a rep acts on first: it says whether the email is safe to send. So it
sorts first, and the competitor link orders rows WITHIN a band.
"""

from authority_finder.output.csv_writer import dedupe_and_sort
from authority_finder.output.models import OutputRow


def _row(
    *, trust: str, links: str = "—", pop: int | None = None, geo: str = "Ohio", site: str = "x.gov"
) -> OutputRow:
    return OutputRow(
        website=site,
        specific_page=f"https://{site}/",
        email="",
        phone="",
        contact_source="",
        contact_trust=trust,
        organization_description="",
        geo_served=geo,
        population=pop,
        competitor_links=links,
        source_tag="MHD",
        date_added="2026-08-06",
        confidence="low",
    )


def _trusts(rows: list[OutputRow]) -> list[str]:
    return [r.contact_trust for r in dedupe_and_sort(rows)]


class TestTrustLeads:
    def test_high_without_a_link_beats_medium_with_one(self) -> None:
        """The exact complaint: this pair was inverted."""
        medium_linked = _row(trust="medium", links="samhsa.gov", site="a.gov")
        high_plain = _row(trust="high", site="b.gov")
        assert _trusts([medium_linked, high_plain]) == ["high", "medium"]

    def test_full_band_ordering(self) -> None:
        rows = [
            _row(trust="low", links="samhsa.gov", site="a.gov"),
            _row(trust="high", site="b.gov"),
            _row(trust="medium", links="samhsa.gov", site="c.gov"),
            _row(trust="low", site="d.gov"),
            _row(trust="high", links="samhsa.gov", site="e.gov"),
            _row(trust="medium", site="f.gov"),
        ]
        assert _trusts(rows) == ["high", "high", "medium", "medium", "low", "low"]

    def test_the_trust_column_never_goes_back_up(self) -> None:
        """A reader scanning the column must see one clean high->medium->low run."""
        rank = {"high": 0, "medium": 1, "low": 2}
        rows = [
            _row(trust=t, links=lk, site=f"{i}.gov")
            for i, (t, lk) in enumerate(
                [
                    ("low", "samhsa.gov"),
                    ("high", "—"),
                    ("medium", "samhsa.gov"),
                    ("high", "samhsa.gov"),
                    ("low", "—"),
                    ("medium", "—"),
                ]
            )
        ]
        seen = [rank[t] for t in _trusts(rows)]
        assert seen == sorted(seen)


class TestSecondaryKeys:
    def test_within_a_band_the_linked_row_leads(self) -> None:
        plain = _row(trust="high", site="a.gov")
        linked = _row(trust="high", links="samhsa.gov", site="b.gov")
        ordered = dedupe_and_sort([plain, linked])
        assert [r.website for r in ordered] == ["b.gov", "a.gov"]

    def test_then_population_descending(self) -> None:
        small = _row(trust="high", pop=1_000, site="a.gov")
        big = _row(trust="high", pop=9_000_000, site="b.gov")
        assert [r.website for r in dedupe_and_sort([small, big])] == ["b.gov", "a.gov"]

    def test_unknown_population_sorts_last_in_its_band(self) -> None:
        known = _row(trust="high", pop=5, site="a.gov")
        unknown = _row(trust="high", pop=None, site="b.gov")
        assert [r.website for r in dedupe_and_sort([unknown, known])] == ["a.gov", "b.gov"]

    def test_then_geo_alphabetically(self) -> None:
        z = _row(trust="high", pop=10, geo="Wyoming", site="a.gov")
        a = _row(trust="high", pop=10, geo="Alabama", site="b.gov")
        assert [r.geo_served for r in dedupe_and_sort([z, a])] == ["Alabama", "Wyoming"]


class TestUnchangedBehaviour:
    def test_dedupe_still_keeps_one_row_per_domain_and_geo(self) -> None:
        a = _row(trust="low", site="dup.gov", geo="Ohio")
        b = _row(trust="high", site="dup.gov", geo="Ohio")
        out = dedupe_and_sort([a, b])
        assert len(out) == 1
        assert out[0].contact_trust == "high", "the best row must survive dedupe"
