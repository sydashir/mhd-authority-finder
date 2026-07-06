"""Domain-based geography derivation. Pure, no network.

candidate_state derives a .gov/.us domain's US state slug ONLY where it's reliable
(state portals + county{abbr}); everything ambiguous returns None (text fallback).
"""

from authority_finder.page_detector.geography import candidate_state


def test_state_portal_subdomain_resolves_to_state() -> None:
    assert candidate_state("https://dol.ny.gov/about") == "new-york"
    assert candidate_state("https://cdph.ca.gov/programs") == "california"


def test_full_name_state_portal_resolves() -> None:
    assert candidate_state("https://hhs.texas.gov/services") == "texas"
    assert candidate_state("https://health.maryland.gov/bha") == "maryland"


def test_county_abbr_suffix_resolves_to_that_state() -> None:
    # A county domain always encodes its OWN state; the "county" anchor makes the abbr reliable.
    assert candidate_state("https://wyomingcountyny.gov/") == "new-york"
    assert candidate_state("https://tarrantcountytx.gov/") == "texas"
    assert candidate_state("https://tetoncountywy.gov/") == "wyoming"


def test_us_municipal_state_from_suffix() -> None:
    assert candidate_state("https://co.orange.ca.us/health") == "california"


def test_edu_is_not_derivable() -> None:
    assert candidate_state("https://cornell.edu/") is None
    assert candidate_state("https://memphis.edu/") is None


def test_bare_city_abbr_is_not_derived() -> None:
    # napa.gov ends in 'pa' (Pennsylvania) but Napa is California — deriving it would misfire.
    assert candidate_state("https://napa.gov/") is None
    assert candidate_state("https://torranceca.gov/") is None


def test_full_state_name_suffix_is_not_derived() -> None:
    # Port Washington is in NY/WI, not Washington state — an endswith match would misfire.
    assert candidate_state("https://portwashington.gov/") is None


def test_cryptic_acronym_is_not_derived() -> None:
    assert (
        candidate_state("https://dconc.gov/") is None
    )  # Durham County NC, but 'dconc' is not derivable
