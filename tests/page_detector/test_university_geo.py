"""University (.edu) domain → state(s) resolution (ADR-024, bucket A)."""

from authority_finder.page_detector.university_geo import university_states


def test_single_state_university() -> None:
    assert university_states("https://www.vaughn.edu/counseling") == frozenset({"new-york"})


def test_uwyo_is_wyoming() -> None:
    assert university_states("uwyo.edu") == frozenset({"wyoming"})


def test_multi_campus_university_maps_to_a_set() -> None:
    # Midwestern University has campuses in both Illinois and Arizona.
    assert university_states("https://midwestern.edu/") == frozenset({"arizona", "illinois"})


def test_unknown_edu_is_none_not_fabricated() -> None:
    assert university_states("https://not-a-real-school-xyz.edu/") is None


def test_non_edu_is_none() -> None:
    # .gov / .us geography is handled elsewhere; this resolver is .edu-only.
    assert university_states("https://county.gov/health") is None


def test_bare_domain_and_subdomain_resolve() -> None:
    assert university_states("news.cornell.edu") == frozenset({"new-york"})
