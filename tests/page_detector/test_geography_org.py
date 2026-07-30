"""Geo derivation for non-.gov candidates (ADR-028).

ADR-020 only derived a state from `.gov`/`.us`, which was right while every candidate was
`.gov`/`.edu`. Component 3's authority source is mostly `.org`/`.com`, so that gate did
nothing for the majority of new candidates — and `mhaorangeny.com` (Mental Health Association
of Orange County NEW YORK) reached output filed under Orange County, CALIFORNIA.

Two-letter state codes are the danger here: `in`, `or`, `me`, `ok`, `hi`, `de`, `la`, `ma`,
`pa`, `co`, `id`, `mt` are all common English fragments. A substring match would be a disaster
generator, so a bare code is only ever read as an anchored suffix on a recognised stem.
Anything ambiguous returns None and falls back to page text — a wrong assertion is worse than
no assertion.
"""

import pytest

from authority_finder.page_detector.geography import candidate_state


class TestTheRealDefect:
    def test_mhaorangeny_com_resolves_to_new_york(self) -> None:
        """The row that reached output under Orange County, California."""
        assert candidate_state("https://mhaorangeny.com/") == "new-york"


class TestFullStateNames:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://northalabamamentalhealthcoalition.org/", "alabama"),
            ("https://alabamamentalhealth.org/", "alabama"),
            ("https://coveralabama.org/", "alabama"),
            ("https://westalabamaaging.org/", "alabama"),
            ("https://thearcoftexas.org/", "texas"),
            ("https://bewelltexas.org/", "texas"),
            ("https://texasseniorsolutions.com/", "texas"),
        ],
    )
    def test_full_state_name_in_the_domain(self, url: str, expected: str) -> None:
        assert candidate_state(url) == expected


class TestTwoLetterCodes:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://naswnc.org/", "north-carolina"),
            ("https://naswtx.org/", "texas"),
            ("https://arcnc.org/", "north-carolina"),
            ("https://apnc.org/", "north-carolina"),
        ],
    )
    def test_recognised_code_patterns(self, url: str, expected: str) -> None:
        assert candidate_state(url) == expected

    @pytest.mark.parametrize("url", ["https://txcouncil.com/", "https://nccdd.org/"])
    def test_a_leading_code_asserts_nothing(self, url: str) -> None:
        """`tx`/`nc` here are PREFIXES, and reading them would be a substring match.

        txcouncil.com is the clearest argument for refusing: its SUFFIX is "il", so a
        naive suffix rule would file the Texas Council of Community Centers under Illinois.
        None is correct — the text heuristic takes over.
        """
        assert candidate_state(url) is None


class TestCollisionTraps:
    """Each of these CONTAINS a valid two-letter state code and is NOT that state.

    A substring match would assert a wrong state for every one of them, and a wrong state
    causes a hard reject — deleting a real prospect.
    """

    @pytest.mark.parametrize(
        "url",
        [
            "https://information.org/",  # 'in' Indiana, 'or' Oregon, 'ma' Massachusetts
            "https://recovery.org/",  # 'co' Colorado, 'or' Oregon
            "https://medicare.org/",  # 'me' Maine, 'ca' California
            "https://booking-services.org/",  # 'ok' and 'in' inside words
            "https://pathways.org/",  # 'pa' Pennsylvania, 'hi' Hawaii
            "https://lacounty-vendor.com/",  # 'la' Louisiana
            "https://identity.org/",  # 'id' Idaho, 'de' Delaware
            "https://community.org/",  # 'co' , 'mm'
            "https://montana-themed-cafe-in-ohio.com/",  # ambiguous, two names
        ],
    )
    def test_ambiguous_domain_asserts_nothing(self, url: str) -> None:
        result = candidate_state(url)
        assert result is None, f"{url} wrongly asserted {result}"


class TestKnownLimitation:
    def test_a_full_state_name_used_as_a_street_name_is_a_false_positive(self) -> None:
        """Accepted limitation, recorded rather than hidden.

        A clinic on Delaware Street resolves to Delaware. Full names are a far stronger
        signal than two-letter codes and are worth keeping, but they cannot distinguish a
        state from a street or a person. The blast radius is one hard-rejected candidate in
        a geo that is not Delaware; the text heuristic cannot rescue it. If this shows up in
        real data, require the name to be adjacent to an org token rather than anywhere.
        """
        assert candidate_state("https://delaware-street-clinic.org/") == "delaware"


class TestExistingBehaviourUnchanged:
    """ADR-020's rules must survive untouched."""

    def test_state_portal_gov(self) -> None:
        assert candidate_state("https://hhs.texas.gov/") == "texas"

    def test_county_abbr_gov(self) -> None:
        assert candidate_state("https://wyomingcountyny.gov/") == "new-york"

    def test_municipal_us(self) -> None:
        assert candidate_state("https://co.orange.ca.us/") == "california"

    def test_bare_city_abbr_gov_still_refuses(self) -> None:
        """napa.gov ends in 'pa' but is California — must stay None."""
        assert candidate_state("https://napa.gov/") is None

    def test_edu_still_refuses(self) -> None:
        """.edu geography is handled by the College Scorecard dataset (ADR-024), not here."""
        assert candidate_state("https://uwyo.edu/") is None

    def test_known_gov_override(self) -> None:
        assert candidate_state("https://dconc.gov/") == "north-carolina"
