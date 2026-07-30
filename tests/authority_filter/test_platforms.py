"""Type-filtering before scoring. Every case below is a domain the LIVE run actually surfaced."""

from authority_finder.authority_filter.filter import select_scoreable
from authority_finder.authority_filter.platforms import PLATFORM_DOMAINS, is_platform


class TestRealSurfacedJunk:
    """These exact domains came back from the unrestricted Alabama/Texas queries at DR 91-100.

    A DR floor cannot remove them — that is the point. facebook.com is maximally
    authoritative and worthless as an outreach prospect.
    """

    def test_social_platforms_are_blocked(self) -> None:
        for domain in ("facebook.com", "instagram.com", "linkedin.com"):
            assert is_platform(domain), domain

    def test_review_and_listing_aggregators_are_blocked(self) -> None:
        assert is_platform("yelp.com")

    def test_pr_newswires_are_blocked(self) -> None:
        assert is_platform("prnewswire.com")

    def test_nonprofit_data_aggregators_are_blocked(self) -> None:
        """guidestar DR 91 and causeiq DR 70 — they list orgs, they are not orgs."""
        assert is_platform("guidestar.org")
        assert is_platform("causeiq.com")

    def test_trade_press_is_blocked(self) -> None:
        assert is_platform("beckersbehavioralhealth.com")

    def test_subdomains_of_a_platform_are_blocked(self) -> None:
        assert is_platform("business.facebook.com")
        assert is_platform("m.yelp.com")


class TestRealOrgsSurvive:
    """The ncala.org class must pass untouched — including .com ones."""

    def test_state_and_regional_councils_survive(self) -> None:
        for domain in (
            "sacada.org",
            "etcada.com",
            "alabamacouncil.org",
            "northalabamamentalhealthcoalition.org",
            "councilonrecovery.org",
            "ntbha.org",
        ):
            assert not is_platform(domain), domain

    def test_a_legitimate_org_on_a_dot_com_survives(self) -> None:
        """txcouncil.com is the Texas Council of Community Centers — a real body on a .com.

        This is why the blocklist is an explicit list and never a TLD or
        'looks-commercial' heuristic.
        """
        assert not is_platform("txcouncil.com")

    def test_national_bodies_survive(self) -> None:
        assert not is_platform("naadac.org")
        assert not is_platform("thementalhealthcoalition.org")


class TestBlocklistShape:
    def test_entries_are_bare_registrable_domains(self) -> None:
        for entry in PLATFORM_DOMAINS:
            assert entry == entry.lower()
            assert not entry.startswith(("http", "www."))
            assert "/" not in entry


class TestAppliedBeforeScoring:
    """The cost half of the argument: a blocked domain must never reach an Ahrefs call."""

    def test_platforms_are_excluded_from_scoreable(self) -> None:
        result = select_scoreable(
            ["facebook.com", "guidestar.org", "sacada.org", "yelp.com"],
        )
        assert result.scoreable == ["sacada.org"]
        assert set(result.skipped_platform) == {"facebook.com", "guidestar.org", "yelp.com"}

    def test_subdomain_collapses_to_registrable_before_scoring(self) -> None:
        """account.texashealth.org burned a slot last run; one org should cost one lookup."""
        result = select_scoreable(
            ["account.texashealth.org", "www.texashealth.org", "texashealth.org"],
        )
        assert result.scoreable == ["texashealth.org"]

    def test_skip_counts_are_reported_for_instrumentation(self) -> None:
        result = select_scoreable(["facebook.com", "hhs.nd.gov", "rehabs.com", "sacada.org"])
        assert len(result.skipped_platform) == 1
        assert len(result.skipped_domain_class) == 1
        assert len(result.skipped_competitor) == 1
        assert len(result.scoreable) == 1
