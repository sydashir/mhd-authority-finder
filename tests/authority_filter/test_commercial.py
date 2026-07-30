"""Commercial-treatment-provider detection, tested against REAL surfaced text.

Every string in `tests/fixtures/authority_snippets.json` is a real title/snippet from the
live SerpAPI cache for a domain the Session 30 validation actually surfaced. No invented
marketing copy — the whole point is that this filter survives contact with real pages.

Precision policy (session brief): filtering out a real coalition is worse than admitting one
facility. So the legitimate set is the hard constraint; the commercial set is best-effort and
its misses are reported honestly rather than forced through with brittle rules.
"""

import json
from pathlib import Path

import pytest

from authority_finder.authority_filter.commercial import is_commercial_provider

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "authority_snippets.json").read_text()
)
COMMERCIAL: dict[str, dict[str, str]] = FIXTURE["commercial"]
LEGITIMATE: dict[str, dict[str, str]] = FIXTURE["legitimate"]

# Aggregator directories that merely LIST a real council. They are junk, but they are junk of
# a different kind — the platform blocklist owns them, not the content detector.
AGGREGATORS = {"rehab.com", "recovered.org"}
# A B2B compliance vendor, not a treatment facility. Also not this detector's job.
VENDORS = {"behavehealth.com"}
# KNOWN MISS, accepted deliberately. markbehavioral.com reads "Mental Health Treatment in
# Clearwater | Call MBH Today" — one CTA and no facility self-description. Catching it would
# mean treating "mental health treatment" as decisive, and a real behavioral-health nonprofit
# can legitimately say that (unlike "treatment center"). Under the stated policy — losing a
# real coalition costs more than admitting one facility — the miss is the cheaper error.
KNOWN_MISSES = {"markbehavioral.com"}


def _text(entry: dict[str, str]) -> tuple[str, str]:
    return entry["title"], entry["snippet"]


class TestLegitimateOrgsSurvive:
    """The hard constraint. A false positive here loses a real prospect."""

    @pytest.mark.parametrize("domain", sorted(LEGITIMATE))
    def test_legitimate_org_is_not_flagged(self, domain: str) -> None:
        title, snippet = _text(LEGITIMATE[domain])
        assert not is_commercial_provider(title=title, snippet=snippet), (
            f"{domain} wrongly flagged commercial\n  title: {title}\n  snippet: {snippet}"
        )


class TestFacilitiesAreFlagged:
    @pytest.mark.parametrize(
        "domain", sorted(set(COMMERCIAL) - AGGREGATORS - VENDORS - KNOWN_MISSES)
    )
    def test_treatment_facility_is_flagged(self, domain: str) -> None:
        title, snippet = _text(COMMERCIAL[domain])
        assert is_commercial_provider(title=title, snippet=snippet), (
            f"{domain} slipped through\n  title: {title}\n  snippet: {snippet}"
        )


class TestSignalDesign:
    def test_a_facility_self_description_alone_is_enough(self) -> None:
        """'treatment center' is a facility describing itself — no CTA needed."""
        assert is_commercial_provider(title="La Hacienda Treatment Center", snippet="")

    def test_a_single_phone_number_is_not_enough(self) -> None:
        """Real orgs publish phone numbers. One contact detail must never flag a row."""
        assert not is_commercial_provider(
            title="Directions for Living, Inc.",
            snippet="1437 S Belcher Rd Clearwater, FL 33764. Phone: (727) 524-4464",
        )

    def test_the_word_recovery_alone_is_not_enough(self) -> None:
        """etcada.com offers 'recovery support services' and is a real council."""
        assert not is_commercial_provider(
            title="ETCADA: Prevention, Assessment, Recovery, & Transition Services",
            snippet="offer recovery support services, diminish substance use through education",
        )

    def test_the_word_facilities_alone_is_not_enough(self) -> None:
        """coalitionoc.org 'supports a network of facilities' and is a real coalition."""
        assert not is_commercial_provider(
            title="Coalition of Orange County Community Health Centers",
            snippet="supports a network of facilities that serve over 340000 patients annually.",
        )

    def test_two_direct_response_ctas_flag_without_a_facility_term(self) -> None:
        """narconon-suncoast.org has no 'treatment center' phrase, just hard CTAs."""
        assert is_commercial_provider(
            title="Narconon Suncoast - Clearwater, Florida",
            snippet="Get Help Now. call 877-850-7355 for drug addiction help. or click here",
        )

    def test_empty_input_is_not_commercial(self) -> None:
        assert not is_commercial_provider(title="", snippet="")

    def test_the_known_miss_is_still_a_miss(self) -> None:
        """Pins the accepted trade-off so a future change to it is a deliberate decision."""
        entry = COMMERCIAL["markbehavioral.com"]
        assert not is_commercial_provider(title=entry["title"], snippet=entry["snippet"])
