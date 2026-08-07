"""Bucketing an outbound domain into directory / support-group classes (ADR-039).

Three rules decide everything here, and each exists because of a measured failure:

1. EXACT registrable domain, never substring. Measured on the delivered corpus: 62 domains
   contain "aa" and 103 contain "na" in their label — `aaaphx.org` and `aaact.org` are Area
   Agencies on Aging, which are the client's OWN target prospects. Substring matching would
   misfire on 165 real rows.
2. Seed only what was verified live. `alateen.org` is on the client's own page and is DEAD
   (connection refused); `recovery-inc.org` is an unrelated UK content site, not Recovery
   International. Harvesting domains from client pages learns broken ones.
3. Unknown is a valid answer. Crisis lines, 211-style general directories and advocacy bodies
   like NAMI need a rubric the client has not written yet, so they stay unclassified rather
   than being guessed into a bucket.
"""

from authority_finder.domains import COMPETITOR_DOMAINS
from authority_finder.link_checker.classify import (
    ADDICTION_DIRECTORIES,
    MENTAL_HEALTH_DIRECTORIES,
    SUPPORT_GROUPS,
    LinkClass,
    classify_domain,
)


class TestTheClientsComplaint:
    """drugrehab.com was missed because it is not one of the brief's 16."""

    def test_drugrehab_com_is_now_an_addiction_directory(self) -> None:
        assert classify_domain("drugrehab.com") is LinkClass.addiction_directory

    def test_the_contractual_sixteen_still_classify(self) -> None:
        for domain in ("samhsa.gov", "recovery.com", "rehabs.com", "findtreatment.gov"):
            assert classify_domain(domain) is LinkClass.addiction_directory, domain


class TestSupportGroups:
    def test_the_national_fellowships_classify(self) -> None:
        for domain in (
            "aa.org",
            "na.org",
            "al-anon.org",
            "smartrecovery.org",
            "womenforsobriety.org",
            "gamblersanonymous.org",
        ):
            assert classify_domain(domain) is LinkClass.support_group, domain

    def test_the_dead_domain_is_not_seeded(self) -> None:
        """alateen.org refuses connections; the live Alateen content is under al-anon.org."""
        assert "alateen.org" not in SUPPORT_GROUPS
        assert classify_domain("alateen.org") is LinkClass.unknown

    def test_the_wrong_org_is_not_seeded(self) -> None:
        """recovery-inc.org is an unrelated UK site, NOT Recovery International."""
        assert "recovery-inc.org" not in SUPPORT_GROUPS
        assert classify_domain("recovery-inc.org") is LinkClass.unknown

    def test_the_unverified_four_are_held_back(self) -> None:
        """Live but bot-blocked, so never confirmed. Await a human check before seeding."""
        for domain in ("coda.org", "oa.org", "nicotine-anonymous.org", "slaafws.org"):
            assert domain not in SUPPORT_GROUPS, domain
            assert classify_domain(domain) is LinkClass.unknown, domain


class TestExactMatchingOnly:
    """The measured failure this guards: 165 real prospects contain 'aa'/'na' in their label."""

    def test_area_agencies_on_aging_are_not_alcoholics_anonymous(self) -> None:
        for domain in ("aaaphx.org", "aaact.org", "aaccw.org", "nekaaa.org", "swcaa.org"):
            assert classify_domain(domain) is LinkClass.unknown, domain

    def test_a_domain_merely_containing_a_seed_does_not_match(self) -> None:
        assert classify_domain("notaa.org") is LinkClass.unknown
        assert classify_domain("aa.org.evil.com") is LinkClass.unknown
        assert classify_domain("mydrugrehab.com") is LinkClass.unknown

    def test_a_subdomain_of_a_seed_still_matches(self) -> None:
        """Callers pass a registrable domain, so this is about normalisation, not substrings."""
        assert classify_domain("www.aa.org") is LinkClass.support_group
        assert classify_domain("WWW.DrugRehab.COM") is LinkClass.addiction_directory


class TestAmbiguousStaysUnknown:
    """Deliberately unclassified until the client writes a rubric (ADR-039)."""

    def test_crisis_lines_and_general_directories_are_not_guessed(self) -> None:
        for domain in (
            "988lifeline.org",
            "211.org",
            "nami.org",
            "crisistextline.org",
            "thetrevorproject.org",
        ):
            assert classify_domain(domain) is LinkClass.unknown, domain

    def test_ordinary_domains_are_unknown(self) -> None:
        for domain in ("ucr.edu", "facebook.com", "example.com", ""):
            assert classify_domain(domain) is LinkClass.unknown, domain


class TestSeedHygiene:
    def test_the_three_seed_sets_do_not_overlap(self) -> None:
        assert not ADDICTION_DIRECTORIES & SUPPORT_GROUPS
        assert not ADDICTION_DIRECTORIES & MENTAL_HEALTH_DIRECTORIES
        assert not MENTAL_HEALTH_DIRECTORIES & SUPPORT_GROUPS

    def test_every_seed_is_lowercase_and_registrable(self) -> None:
        for seed in ADDICTION_DIRECTORIES | SUPPORT_GROUPS | MENTAL_HEALTH_DIRECTORIES:
            assert seed == seed.lower(), seed
            assert not seed.startswith("www."), seed
            assert "/" not in seed and " " not in seed, seed
            assert seed.count(".") >= 1, seed

    def test_the_contractual_sixteen_are_all_present(self) -> None:
        """COMPETITOR_DOMAINS is the brief's contract; the addiction bucket must be a superset."""
        assert COMPETITOR_DOMAINS <= ADDICTION_DIRECTORIES
