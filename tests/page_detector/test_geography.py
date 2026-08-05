"""Domain-based geography derivation. Pure, no network.

candidate_state derives a .gov/.us domain's US state slug ONLY where it's reliable
(state portals + county{abbr}); everything ambiguous returns None (text fallback).
"""

import pytest

from authority_finder.page_detector.geography import candidate_state


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        # S19 regression cases (data/output/s19-sample-v2.csv):
        ("wyomingcountyny.gov", "new-york"),  # served to Wyoming — the killer wrong-state case
        ("steubencountyny.gov", "new-york"),  # correctly a NY county
        ("tarrantcountytx.gov", "texas"),
        ("tetoncountywy.gov", "wyoming"),
        ("oasas.ny.gov", "new-york"),  # state-portal subdomain
        ("edu.wyoming.gov", "wyoming"),  # full-name portal
        ("cornell.edu", None),  # NY university — not domain-derivable
        ("memphis.edu", None),  # TN university
        ("cuanschutz.edu", None),  # CO campus
        ("dconc.gov", "north-carolina"),  # Durham County NC — a verified override (ADR-025)
        # 'oc' is not a state abbr and used to fall through to text; the registry knows it.
        ("oc.gov", "california"),  # County of Orange (ADR-035)
    ],
)
def test_s19_real_domains(domain: str, expected: str | None) -> None:
    assert candidate_state(f"https://{domain}/") == expected


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


def test_bare_city_abbr_is_never_guessed_from_the_string() -> None:
    # napa.gov ends in 'pa' (Pennsylvania) but Napa is California. The string rules must still
    # refuse to guess: the registry does not cover this domain, so nothing is asserted.
    assert candidate_state("https://napa.gov/") is None


def test_the_registry_answers_where_the_string_rules_cannot() -> None:
    """ADR-035: CISA is the registrar, so where it answers it beats any string heuristic.

    Both of these used to return None — correctly, because the suffix is a trap — and the
    cost was that a wrong-state row could not be rejected. Now they are known, not guessed.
    """
    assert candidate_state("https://torranceca.gov/") == "california"  # City of Torrance
    assert candidate_state("https://cabq.gov/") == "new-mexico"  # City of Albuquerque


def test_full_state_name_suffix_is_not_derived() -> None:
    # Port Washington is in NY/WI, not Washington state — an endswith match would misfire.
    assert candidate_state("https://portwashington.gov/") is None


def test_a_cryptic_acronym_outside_the_registry_is_still_not_derived() -> None:
    """The anti-guessing rule survives: no registry row, no assertion."""
    assert candidate_state("https://portwashington.gov/") is None


def test_verified_cryptic_gov_override_is_derived() -> None:
    # dconc.gov is Durham County NC (verified in the QA audit) — a small override lets the scorer
    # hard-reject it when served to a non-NC geo (it slipped through as wrong-geo, ADR-025).
    assert candidate_state("https://dconc.gov/") == "north-carolina"
    assert candidate_state("https://www.dconc.gov/behavioral-health/") == "north-carolina"
