"""Email extraction: mailto/body, obfuscation, false-positive guards, ranking.

The false-positive cases are the adversarial-audit findings (ADR-007) pinned as
regressions — this is precision-critical, so a wrong email is a test failure.
"""

import pytest

from authority_finder.contact_extractor.extract import (
    deobfuscate,
    extract_emails,
    rank_emails,
)
from tests.contact_extractor.conftest import page


def addrs(content_kwargs: dict[str, object]) -> list[str]:
    return [e.address for e in rank_emails(extract_emails(page(**content_kwargs)))]  # type: ignore[arg-type]


def test_mailto_extracted_highest_confidence() -> None:
    hits = extract_emails(page(mailto=["BehavioralHealth@county.gov"]))
    assert len(hits) == 1
    assert hits[0].address == "behavioralhealth@county.gov"
    assert hits[0].source == "mailto"
    assert hits[0].confidence == 1.0  # 0.9 base + 0.1 dept, rounded to 2dp


def test_body_text_email_extracted() -> None:
    assert addrs({"text": "Email health@county.gov for help."}) == ["health@county.gov"]


def test_trailing_period_does_not_break_match() -> None:
    assert addrs({"text": "Write to clerk@city.gov."}) == ["clerk@city.gov"]


def test_role_account_deprioritized_not_dropped() -> None:
    hits = extract_emails(page(mailto=["webmaster@county.gov"]))
    assert hits[0].address == "webmaster@county.gov"
    assert hits[0].confidence == 0.5  # 0.9 - 0.4


def test_contact_page_source_label() -> None:
    hits = extract_emails(page(mailto=["info@county.gov"]), contact_page=True)
    assert hits[0].source == "contact_page"


@pytest.mark.parametrize(
    "text",
    [
        "render {{dept@county.gov}} here",
        "Send to ${admin@host.local} now.",
        "DSN https://abc123@o45.ingest.sentry.io/123",
        "crate serde@1.0.gov build",
        "pin react@18.2.org now",
        "open config@settings.ts file",
        "key AKIA9@SECRET.key value",
        "data:image/png;base64,iVBOR@w0KGgo.bAAANS here",
        "logo@2x.png and icon@3x.svg",
        "placeholder you@example.com and name@domain.com",
    ],
)
def test_email_false_positives_rejected(text: str) -> None:
    assert addrs({"text": text}) == []


def test_zip_phone_glued_into_local_part_rejected() -> None:
    # Live defect: address ran together with a ZIP + phone, no separator.
    assert addrs({"text": "Denver CO 80204303-315-2228spa.admissions@ucdenver.edu"}) == []


def test_short_digit_local_parts_survive() -> None:
    assert addrs({"text": "Reach covid19@county.gov or team211@county.gov."}) == [
        "covid19@county.gov",
        "team211@county.gov",
    ]


def test_real_emails_survive_the_guards() -> None:
    assert addrs({"text": "Reach intake+referrals@dhs.ca.gov or info@mail.county.gov."}) == [
        "info@mail.county.gov",
        "intake+referrals@dhs.ca.gov",
    ]


def test_multi_segment_spelled_obfuscation() -> None:
    assert deobfuscate("info at mail dot county dot gov") == "info@mail.county.gov"
    assert addrs({"text": "info at mail dot county dot gov"}) == ["info@mail.county.gov"]


def test_us_county_spelled_obfuscation() -> None:
    assert addrs({"text": "intake at co dot santa-clara dot ca dot us"}) == [
        "intake@co.santa-clara.ca.us"
    ]


def test_bracket_obfuscation() -> None:
    assert addrs({"text": "info [at] county [dot] gov"}) == ["info@county.gov"]


def test_prose_with_at_and_dot_not_mangled() -> None:
    assert addrs({"text": "Meet at noon. The dot product is zero."}) == []


def test_dept_localpart_outranks_role_account() -> None:
    hits = extract_emails(page(mailto=["webmaster@county.gov", "behavioralhealth@county.gov"]))
    ranked = rank_emails(hits)
    assert ranked[0].address == "behavioralhealth@county.gov"
    assert ranked[-1].address == "webmaster@county.gov"


def test_mailto_outranks_body_at_equal_confidence() -> None:
    content = page(text="staff aaron.k.miller@dhs.ca.gov", mailto=["hostmaster@dhs.ca.gov"])
    ranked = rank_emails(extract_emails(content))
    # hostmaster (mailto 0.5) ties aaron (body 0.5); mailto wins the tie-break.
    assert ranked[0].address == "hostmaster@dhs.ca.gov"
