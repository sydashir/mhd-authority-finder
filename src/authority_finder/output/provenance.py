"""Contact provenance: a human-readable source label and a trust band, derived
from a :class:`ContactSet` (ADR-009).

These answer "can outreach trust this contact" — separate from the page-detection
Confidence, which only rates how well the page matches the geo. The primary
contact is the best email if any, else the best phone.
"""

from authority_finder.contact_extractor.models import ContactSet, EmailHit, EmailSource

# Department-meaningful local-parts → a contact you'd actually email for outreach.
_DEPT_LOCALPARTS = frozenset(
    {
        "health",
        "behavioralhealth",
        "mentalhealth",
        "publichealth",
        "counseling",
        "contact",
        "info",
        "recovery",
        "intake",
        "referrals",
        "wellness",
    }
)

_SOURCE_LABELS: dict[EmailSource, str] = {
    "mailto": "mailto (same-domain)",
    "body_text": "body-text (same-domain)",
    "contact_page": "contact-page hop",
}


def _dept_localpart(address: str) -> bool:
    local = address.split("@", 1)[0].lower()
    head = local.replace(".", "").replace("_", "").replace("-", "")
    return local in _DEPT_LOCALPARTS or head in _DEPT_LOCALPARTS


def contact_source_label(contacts: ContactSet) -> str:
    """Provenance of the row's primary contact: e.g. 'mailto (same-domain)', 'tel'."""
    if contacts.emails:
        email = contacts.emails[0]
        if email.source == "mailto":
            return "mailto (same-domain)" if email.same_domain else "mailto (off-domain)"
        return _SOURCE_LABELS[email.source]
    if contacts.phones:
        source = contacts.phones[0].source
        return {"tel": "tel", "contact_page": "contact-page hop", "body_text": "body-text phone"}[
            source
        ]
    return ""


def contact_trust(contacts: ContactSet) -> str:
    """Trust band for the row's primary contact (high / medium / low)."""
    if contacts.emails:
        return _email_trust(contacts.emails[0])
    return "low"  # phone-only or nothing — never high-trust for outreach


def _email_trust(email: EmailHit) -> str:
    dept = _dept_localpart(email.address)
    if email.source == "mailto":
        if not email.same_domain:
            return "low"  # cross-domain mailto = a third-party org (e.g. info@frsn.org)
        return "high" if dept else "medium"
    if email.source == "contact_page":
        return "medium" if dept else "low"
    return "medium" if dept else "low"  # body_text (same-domain by construction), weaker
