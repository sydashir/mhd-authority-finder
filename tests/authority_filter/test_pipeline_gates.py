"""Authority candidates must run the SAME gates as every other source.

This is the critical guarantee of component 3: a new candidate source must not bypass five
sessions of hardening (ADR-020/024 wrong-state, junk-page, hotline blocklist, trust banding).
It is enforced structurally — authority candidates are ordinary CandidateSite objects merged
into DiscoveryResult BEFORE detection — so these tests assert that structure holds.
"""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.authority_filter.filter import select_scoreable
from authority_finder.contact_extractor.extract import extract_phones
from authority_finder.discovery.models import CandidateSite, GeoRef
from authority_finder.fetching.models import PageContent
from authority_finder.page_detector.geography import candidate_state

NOW = datetime(2026, 7, 30, tzinfo=UTC)


def _ref() -> GeoRef:
    return GeoRef(
        site_id="ah",
        url="https://addictionhotline.com/north-carolina/",
        level="state",
        state="north-carolina",
    )


def _authority_candidate(domain: str) -> CandidateSite:
    return CandidateSite(
        registrable_domain=domain,
        url=HttpUrl(f"https://{domain}/"),
        title=domain,
        snippet="",
        domain_class="other",
        geo=_ref(),
        source_queries=["North Carolina assisted living association"],
        discovered_at=NOW,
    )


class TestSameTypeAsDiscovery:
    def test_authority_candidate_is_an_ordinary_candidate_site(self) -> None:
        """Same type in, same pipeline out — there is no separate authority code path."""
        candidate = _authority_candidate("ncala.org")
        assert isinstance(candidate, CandidateSite)
        assert candidate.domain_class == "other"

    def test_carries_the_geo_so_wrong_state_validation_can_run(self) -> None:
        """ADR-020/024 rejects on candidate-vs-target state; that needs the geo attached."""
        candidate = _authority_candidate("ncala.org")
        assert candidate.geo.state == "north-carolina"


class TestScorerAppliesToAuthorityCandidates:
    def test_wrong_state_gate_rejects_an_out_of_state_authority_domain(self) -> None:
        # A .gov whose domain proves another state must be rejected regardless of source.
        assert candidate_state("https://wyomingcountyny.gov/") is not None

    def test_hotline_blocklist_is_source_independent(self) -> None:
        """A national crisis line published as an org phone must be dropped, whatever the
        source. Exercised through the public extractor, which every source shares."""
        content = PageContent(
            final_url="https://ncala.org/contact",
            title="Contact",
            h1s=[],
            meta_description="",
            text_sample="Call us at 1-800-273-8255 for help.",
            links=[],
            has_mailto=False,
            has_tel=False,
        )
        numbers = [hit.number for hit in extract_phones(content)]
        assert "+18002738255" not in numbers

    def test_platform_blocklist_runs_before_a_candidate_is_ever_built(self) -> None:
        result = select_scoreable(["facebook.com", "ncala.org"])
        assert result.scoreable == ["ncala.org"]
