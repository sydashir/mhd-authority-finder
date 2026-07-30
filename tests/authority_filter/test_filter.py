"""Which domains get scored, and what passes. Pure logic — no network, no units."""

from authority_finder.authority_filter.ahrefs_client import DomainRating
from authority_finder.authority_filter.filter import (
    DEFAULT_DR_THRESHOLD,
    apply_threshold,
    select_scoreable,
)


class TestSelectScoreable:
    def test_gov_and_edu_are_skipped_so_no_units_are_wasted(self) -> None:
        """.gov/.edu already pass on domain class alone (ADR-006) — never pay to score them."""
        result = select_scoreable(
            ["hhs.nd.gov", "uwyo.edu", "ncala.org"],
        )
        assert result.scoreable == ["ncala.org"]
        assert set(result.skipped_domain_class) == {"hhs.nd.gov", "uwyo.edu"}

    def test_competitor_domains_are_excluded(self) -> None:
        result = select_scoreable(["ncala.org", "rehabs.com", "addictioncenter.com"])
        assert result.scoreable == ["ncala.org"]
        assert set(result.skipped_competitor) == {"rehabs.com", "addictioncenter.com"}

    def test_federal_domains_are_excluded(self) -> None:
        result = select_scoreable(["ncala.org", "samhsa.gov", "irs.gov"])
        # samhsa.gov/irs.gov are federal AND .gov; either way they must not be scored.
        assert result.scoreable == ["ncala.org"]

    def test_deduplicates_and_normalises(self) -> None:
        result = select_scoreable(
            ["https://ncala.org/about", "www.ncala.org", "NCALA.ORG"],
        )
        assert result.scoreable == ["ncala.org"]

    def test_subdomain_of_a_competitor_is_still_excluded(self) -> None:
        """Registrable-domain matching, per ADR-011 — not a substring test."""
        result = select_scoreable(["blog.rehabs.com", "ncala.org"])
        assert result.scoreable == ["ncala.org"]

    def test_a_domain_merely_containing_a_competitor_name_is_kept(self) -> None:
        """rehabsomething.com is not rehabs.com (the ADR-011 false-positive guard)."""
        result = select_scoreable(["rehabsomething.com"])
        assert result.scoreable == ["rehabsomething.com"]


class TestApplyThreshold:
    def _ratings(self) -> dict[str, DomainRating]:
        return {
            "nami.org": DomainRating("nami.org", 90.0, 100),
            "ncala.org": DomainRating("ncala.org", 34.0, 2620675),
            "calbhbc.org": DomainRating("calbhbc.org", 29.0, 5000000),
            "wearesober.org": DomainRating("wearesober.org", 0.0, None),
            "unknown.org": DomainRating("unknown.org", None, None),
        }

    def test_passes_at_or_above_threshold(self) -> None:
        outcome = apply_threshold(self._ratings(), threshold=25)
        assert set(outcome.passed) == {"nami.org", "ncala.org", "calbhbc.org"}

    def test_below_threshold_is_dropped_but_counted(self) -> None:
        """Instrumentation discipline from ADR-006: a drop is recorded, not silent."""
        outcome = apply_threshold(self._ratings(), threshold=25)
        assert outcome.dropped_below_threshold == {"wearesober.org": 0.0}
        assert outcome.dropped_count == 2  # the DR-0 site plus the no-data one

    def test_no_data_is_dropped_separately_from_a_real_zero(self) -> None:
        outcome = apply_threshold(self._ratings(), threshold=25)
        assert outcome.dropped_no_data == ["unknown.org"]
        assert "unknown.org" not in outcome.dropped_below_threshold

    def test_threshold_is_inclusive_at_the_boundary(self) -> None:
        ratings = {"edge.org": DomainRating("edge.org", 25.0, 1)}
        assert apply_threshold(ratings, threshold=25).passed == ["edge.org"]

    def test_the_brief_default_of_40_would_reject_ncala(self) -> None:
        """Documents the calibration finding that motivated lowering the default (ADR-026)."""
        outcome = apply_threshold(self._ratings(), threshold=40)
        assert "ncala.org" not in outcome.passed
        assert outcome.dropped_below_threshold["ncala.org"] == 34.0

    def test_default_threshold_keeps_state_level_orgs(self) -> None:
        outcome = apply_threshold(self._ratings(), threshold=DEFAULT_DR_THRESHOLD)
        assert "ncala.org" in outcome.passed
        assert "calbhbc.org" in outcome.passed

    def test_passed_is_ordered_by_dr_descending(self) -> None:
        outcome = apply_threshold(self._ratings(), threshold=25)
        assert outcome.passed[0] == "nami.org"
