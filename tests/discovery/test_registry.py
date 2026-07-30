"""Registry lookup, tested against domains the LIVE dataset actually found (ADR-029)."""

from authority_finder.discovery.registry import domains_for_geo, load_registry


def _names(rows: list) -> set[str]:
    return {r.domain for r in rows}


class TestRegistryLoads:
    def test_the_vendored_file_is_present_and_parsed(self) -> None:
        rows = load_registry()
        assert len(rows) > 15_000, "vendored CISA registry missing or truncated"

    def test_no_runtime_network_dependency(self) -> None:
        """Loading must work offline — a 3am scheduled run cannot depend on an external host."""
        assert all(r.domain and r.state for r in load_registry()[:50])


class TestRealCasesFromTheLiveDataset:
    def test_county_geo_finds_its_county_domain(self) -> None:
        """pinellas.gov is a County row whose City column is the SEAT (Clearwater)."""
        rows = domains_for_geo(state="florida", county="pinellas")
        assert "pinellas.gov" in _names(rows)

    def test_county_slug_with_the_word_county_still_matches(self) -> None:
        rows = domains_for_geo(state="maryland", county="montgomery-county")
        assert "montgomerycountymd.gov" in _names(rows)

    def test_city_geo_finds_its_city_domain(self) -> None:
        rows = domains_for_geo(state="alabama", city="huntsville")
        assert "huntsvilleal.gov" in _names(rows)

    def test_state_geo_finds_the_state_portal(self) -> None:
        assert "alabama.gov" in _names(domains_for_geo(state="alabama"))
        assert "texas.gov" in _names(domains_for_geo(state="texas"))

    def test_parent_domain_seeds_are_available_for_subdomain_rows(self) -> None:
        """The live dataset found hhs.nd.gov; the registry supplies nd.gov as the seed and
        page_detector's bounded crawl reaches the department page from there."""
        assert "nd.gov" in _names(domains_for_geo(state="north-dakota"))


class TestScoping:
    def test_results_are_confined_to_the_requested_state(self) -> None:
        rows = domains_for_geo(state="alabama", city="huntsville")
        assert {r.state for r in rows} == {"AL"}

    def test_a_city_also_inherits_county_and_state_domains(self) -> None:
        """A county health department is a real prospect for a city page."""
        rows = domains_for_geo(state="florida", county="pinellas", city="clearwater")
        names = _names(rows)
        assert "pinellas.gov" in names

    def test_more_specific_rows_lead(self) -> None:
        rows = domains_for_geo(state="florida", county="pinellas", city="clearwater")
        kinds = [r.kind for r in rows]
        assert kinds.index("County") < kinds.index("State or territory")

    def test_unknown_state_slug_returns_nothing_rather_than_guessing(self) -> None:
        assert domains_for_geo(state="not-a-state") == []

    def test_results_are_deduplicated(self) -> None:
        rows = domains_for_geo(state="florida", county="pinellas", city="clearwater")
        assert len(rows) == len({r.domain for r in rows})
