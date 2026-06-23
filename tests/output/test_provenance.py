"""Contact Source label + Contact Trust banding — derived from a ContactSet."""

from authority_finder.contact_extractor.models import ContactSet, EmailHit, EmailSource, PhoneHit
from authority_finder.output.provenance import contact_source_label, contact_trust


def _e(address: str, source: EmailSource, *, same_domain: bool = True) -> EmailHit:
    return EmailHit(address=address, source=source, confidence=0.0, same_domain=same_domain)


def _emails(*hits: EmailHit) -> ContactSet:
    return ContactSet(emails=list(hits), best_email=hits[0].address if hits else None)


def _phone_only() -> ContactSet:
    hit = PhoneHit(number="+17145551234", raw="(714) 555-1234", source="tel")
    return ContactSet(phones=[hit], best_phone=hit.number)


# --- contact_source_label ---


def test_source_mailto_same_domain() -> None:
    assert (
        contact_source_label(_emails(_e("health@county.gov", "mailto"))) == "mailto (same-domain)"
    )


def test_source_body_text() -> None:
    assert (
        contact_source_label(_emails(_e("health@county.gov", "body_text")))
        == "body-text (same-domain)"
    )


def test_source_contact_page_hop() -> None:
    assert (
        contact_source_label(_emails(_e("info@county.gov", "contact_page"))) == "contact-page hop"
    )


def test_source_tel_when_phone_only() -> None:
    assert contact_source_label(_phone_only()) == "tel"


def test_source_blank_when_no_contact() -> None:
    assert contact_source_label(ContactSet()) == ""


# --- contact_trust ---


def test_trust_high_dept_mailto_same_domain() -> None:
    assert contact_trust(_emails(_e("behavioralhealth@county.gov", "mailto"))) == "high"


def test_trust_medium_generic_mailto() -> None:
    assert contact_trust(_emails(_e("webmaster@county.gov", "mailto"))) == "medium"


def test_trust_medium_dept_contact_page() -> None:
    assert contact_trust(_emails(_e("counseling@uni.edu", "contact_page"))) == "medium"


def test_trust_low_generic_contact_page() -> None:
    # Live case: admissions@ucdenver.edu from a generic university contact-us hop.
    assert contact_trust(_emails(_e("admissions@ucdenver.edu", "contact_page"))) == "low"


def test_trust_low_phone_only() -> None:
    assert contact_trust(_phone_only()) == "low"


def test_trust_low_when_no_contact() -> None:
    assert contact_trust(ContactSet()) == "low"


def test_trust_body_text_dept_is_medium() -> None:
    assert contact_trust(_emails(_e("health@county.gov", "body_text"))) == "medium"


def test_trust_cross_domain_mailto_is_low() -> None:
    # Live: info@frsn.org is a mailto to a THIRD-PARTY org on a county page.
    # Per spec, medium requires same-domain mailto -> cross-domain mailto is low.
    cs = _emails(_e("info@frsn.org", "mailto", same_domain=False))
    assert contact_trust(cs) == "low"


def test_source_cross_domain_mailto_flagged_off_domain() -> None:
    cs = _emails(_e("info@frsn.org", "mailto", same_domain=False))
    assert contact_source_label(cs) == "mailto (off-domain)"
