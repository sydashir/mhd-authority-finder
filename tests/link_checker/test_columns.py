"""Assembling the deliverable's link columns (ADR-041).

The client's complaint: ucr.edu showed samhsa.gov in "Competitor Links" and drugrehab.com in
"Addiction Directories", which reads as two unrelated universes. They are not. A category
column is the FULL list for that category; Competitor Links is a subset flag over it, kept so
the brief's original question ("does this org already link to one of our 16?") stays answerable.

The superset used to hold only by accident — COMPETITOR_DOMAINS happens to be a subset of
ADDICTION_DIRECTORIES, so any live crawl produced consistent columns. Re-classification broke
that: it rebuilds categories from stored domains, and 5 rows whose re-crawl failed kept their
competitor evidence while their category column went blank. These tests make the relationship
structural instead of incidental.
"""

from authority_finder.link_checker.classify import LinkClass
from authority_finder.link_checker.columns import build_link_columns


def _columns(**kwargs: object) -> dict[str, str]:
    base: dict[str, object] = {
        "competitor_domains": [],
        "bucketed": {},
        "support_group_pages": [],
        "all_domains": [],
    }
    return build_link_columns(**(base | kwargs))  # pyright: ignore[reportArgumentType]


class TestTheCategoryColumnIsAlwaysASuperset:
    def test_a_competitor_domain_always_appears_in_the_category_column(self) -> None:
        """The client's exact confusion: a domain in the flag but not in its category."""
        cells = _columns(
            competitor_domains=["samhsa.gov", "addictionresource.net"],
            bucketed={LinkClass.addiction_directory: ["drugrehab.com"]},
        )
        assert cells["addiction_directories"] == (
            "addictionresource.net; drugrehab.com; samhsa.gov"
        )
        assert cells["competitor_links"] == "addictionresource.net; samhsa.gov"

    def test_the_superset_holds_even_when_the_category_is_otherwise_empty(self) -> None:
        """The 5 real rows: re-crawl failed, so stored domains are empty but the flag survives.

        Blanking the category here would tell the client this organisation links to no
        directory while the very next column names one.
        """
        cells = _columns(competitor_domains=["samhsa.gov"], bucketed={})
        assert cells["addiction_directories"] == "samhsa.gov"

    def test_duplicates_across_the_two_sources_collapse(self) -> None:
        cells = _columns(
            competitor_domains=["samhsa.gov"],
            bucketed={LinkClass.addiction_directory: ["samhsa.gov", "drugrehab.com"]},
        )
        assert cells["addiction_directories"] == "drugrehab.com; samhsa.gov"


class TestTheContractualFlagIsUnchanged:
    def test_competitor_links_never_gains_a_learned_domain(self) -> None:
        """It answers the brief's question about the NAMED 16 and must keep meaning that."""
        cells = _columns(
            competitor_domains=["samhsa.gov"],
            bucketed={LinkClass.addiction_directory: ["drugrehab.com", "rehabspot.com"]},
        )
        assert cells["competitor_links"] == "samhsa.gov"

    def test_no_competitor_reads_as_a_dash(self) -> None:
        cells = _columns(bucketed={LinkClass.addiction_directory: ["drugrehab.com"]})
        assert cells["competitor_links"] == "—"
        assert cells["addiction_directories"] == "drugrehab.com"


class TestTheOtherCategories:
    def test_each_category_carries_everything_in_it(self) -> None:
        cells = _columns(
            bucketed={
                LinkClass.support_group: ["na.org", "aa.org"],
                LinkClass.mental_health_directory: ["psychologytoday.com"],
            }
        )
        assert cells["support_groups"] == "aa.org; na.org"
        assert cells["mental_health_directories"] == "psychologytoday.com"

    def test_an_empty_category_reads_as_a_dash(self) -> None:
        cells = _columns()
        for column in ("addiction_directories", "mental_health_directories", "support_groups"):
            assert cells[column] == "—", column

    def test_support_group_provenance_is_blank_not_dashed(self) -> None:
        """Provenance is not a finding; a dash there would read as one."""
        assert _columns()["support_groups_found_on"] == ""
        assert (
            _columns(support_group_pages=["https://x.edu/help"])["support_groups_found_on"]
            == "https://x.edu/help"
        )


class TestRawDomains:
    def test_every_observed_domain_is_stored_deduped_and_sorted(self) -> None:
        cells = _columns(all_domains=["b.org", "a.org", "b.org"])
        assert cells["outbound_domains"] == "a.org; b.org"


class TestNotChecked:
    """A page we could not fetch is not a page with no links (ADR-041 addendum).

    37 delivered rows had these columns genuinely EMPTY while the legend promised
    "never blank". Writing "—" instead would have been worse: that cell means "checked and
    found none", which is a claim about pages nobody ever read. The third state says what
    actually happened.
    """

    def test_an_unchecked_row_says_so_in_every_category(self) -> None:
        cells = _columns(checked=False)
        for column in ("addiction_directories", "mental_health_directories", "support_groups"):
            assert cells[column] == "not checked", column

    def test_not_checked_is_distinct_from_none_found(self) -> None:
        """The whole point: the client must be able to tell these two apart."""
        assert (
            _columns(checked=False)["addiction_directories"] != _columns()["addiction_directories"]
        )
        assert _columns()["addiction_directories"] == "—"

    def test_no_category_cell_is_ever_blank(self) -> None:
        """The legend promises it; this makes the promise structural."""
        for cells in (_columns(), _columns(checked=False), _columns(competitor_domains=["x.gov"])):
            for column in (
                "addiction_directories",
                "mental_health_directories",
                "support_groups",
            ):
                assert cells[column].strip(), column

    def test_surviving_competitor_evidence_still_wins_over_not_checked(self) -> None:
        """If we hold a competitor domain from an earlier run, we DID check once — say so."""
        cells = _columns(checked=False, competitor_domains=["samhsa.gov"])
        assert cells["addiction_directories"] == "samhsa.gov"
        # The classes we have no evidence for stay honest about not having been checked.
        assert cells["support_groups"] == "not checked"

    def test_provenance_stays_blank_when_unchecked(self) -> None:
        """Provenance points at a page; there is nothing to point at."""
        assert _columns(checked=False)["support_groups_found_on"] == ""
