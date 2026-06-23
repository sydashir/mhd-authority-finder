"""Email extraction: mailto/body, obfuscation, false-positive guards, ranking.

The false-positive cases are the adversarial-audit findings (ADR-007) pinned as
regressions — this is precision-critical, so a wrong email is a test failure.
"""

import pytest

from authority_finder.contact_extractor.extract import (
    deobfuscate,
    extract_emails,
    is_dept_localpart,
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
    got = addrs({"final_url": "https://www.city.gov/clerk", "text": "Write to clerk@city.gov."})
    assert got == ["clerk@city.gov"]


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
    # Plus-tags and subdomain-mail hosts aren't junk-rejected (each on its own domain page).
    assert addrs(
        {"final_url": "https://dhs.ca.gov/x", "text": "Reach intake+referrals@dhs.ca.gov today."}
    ) == ["intake+referrals@dhs.ca.gov"]
    assert addrs({"final_url": "https://county.gov/x", "text": "Email info@mail.county.gov."}) == [
        "info@mail.county.gov"
    ]


def test_multi_segment_spelled_obfuscation() -> None:
    assert deobfuscate("info at mail dot county dot gov") == "info@mail.county.gov"
    assert addrs({"text": "info at mail dot county dot gov"}) == ["info@mail.county.gov"]


def test_us_county_spelled_obfuscation() -> None:
    text = "intake at co dot santa-clara dot ca dot us"
    got = addrs({"final_url": "https://co.santa-clara.ca.us/x", "text": text})
    assert got == ["intake@co.santa-clara.ca.us"]


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
    # Same-domain page so the body email survives the domain constraint and the tie is real.
    content = page(
        final_url="https://dhs.ca.gov/staff",
        text="staff aaron.k.miller@dhs.ca.gov",
        mailto=["hostmaster@dhs.ca.gov"],
    )
    ranked = rank_emails(extract_emails(content))
    # hostmaster (mailto 0.5) ties aaron (body 0.5); mailto wins the tie-break.
    assert ranked[0].address == "hostmaster@dhs.ca.gov"


# --- Session 8: domain-constrain body-text emails (wrong-ORG fix) ---


def test_body_text_foreign_domain_email_dropped() -> None:
    # Live defect: info@frsn.org (3rd-party crisis line) on a montgomerycountymd.gov page.
    url = "https://montgomerycountymd.gov/mh"
    assert addrs({"final_url": url, "text": "Crisis line info@frsn.org."}) == []


def test_body_text_same_domain_email_kept() -> None:
    url = "https://montgomerycountymd.gov/mh"
    got = addrs({"final_url": url, "text": "bh@montgomerycountymd.gov"})
    assert got == ["bh@montgomerycountymd.gov"]


def test_body_text_email_carries_same_domain_flag() -> None:
    content = page(final_url="https://county.gov/dept", text="Reach health@county.gov today.")
    hits = extract_emails(content)
    assert hits and hits[0].same_domain is True


def test_mailto_foreign_domain_kept_as_is() -> None:
    # mailto is intentional — not domain-constrained (e.g. fourth.district@ocgov.com on oc.gov).
    content = page(final_url="https://bos4.oc.gov/contact", mailto=["fourth.district@ocgov.com"])
    addresses = [e.address for e in extract_emails(content)]
    assert "fourth.district@ocgov.com" in addresses


def test_contact_page_body_email_not_domain_constrained() -> None:
    # Contact-page hop stays as-is even for body-text (the hop is the trust signal).
    content = page(final_url="https://county.gov/contact", text="Partner: referrals@partnerorg.org")
    hits = extract_emails(content, contact_page=True)
    assert "referrals@partnerorg.org" in [e.address for e in hits]


# --- Session 9: department-relevance predicate (evidence-derived, audit §3) ---


@pytest.mark.parametrize(
    "addr",
    [
        "counseling@uni.edu",
        "ivccounseling@ivc.edu",
        "unccounselingcenter@unco.edu",
        "counselinf@fmu.edu",
        "behavioralhealth@county.gov",
        "recoverysupport@howardcountymd.gov",
        "humansvs@pinellas.gov",
        "frs.peer_support_cism@montgomerycountymd.gov",
        "health@county.gov",
        "mentalhealth@county.gov",
        "studenthealth@uni.edu",
    ],
)
def test_is_dept_localpart_true(addr: str) -> None:
    assert is_dept_localpart(addr)


@pytest.mark.parametrize(
    "addr",
    [
        "admissions@uni.edu",
        "webmaster@county.gov",
        "communications@uci.edu",
        "auditor@longbeach.gov",
        "helpdesk@franklin.edu",
        "careerservices@floridapoly.edu",
        "info@county.gov",  # generic, not dept-specific
        "contact@county.gov",
        "environmentalhealth@longbeach.gov",  # guard: contains 'mentalhealth'
    ],
)
def test_is_dept_localpart_false(addr: str) -> None:
    assert not is_dept_localpart(addr)
