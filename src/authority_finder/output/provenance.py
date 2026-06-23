"""Contact provenance: a human-readable source label and a trust band, derived
from a :class:`ContactSet` (ADR-009).

These answer "can outreach trust this contact" — separate from the page-detection
Confidence, which only rates how well the page matches the geo. The primary
contact is the best email if any, else the best phone.
"""

from authority_finder.contact_extractor.extract import classify_localpart
from authority_finder.contact_extractor.models import ContactSet, EmailHit, EmailSource

_SOURCE_LABELS: dict[EmailSource, str] = {
    "mailto": "mailto (same-domain)",
    "body_text": "body-text (same-domain)",
    "contact_page": "contact-page hop",
}


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
    """Trust band re-derived by department relevance (Session 9, ADR-010 — tightened).

    Off-domain → ``low`` (third-party/sibling org, not this page's own contact); wrong-dept /
    role-noise → ``low`` even as a same-domain mailto; a real same-domain department inbox →
    ``high`` (mailto) or ``medium`` (reached via a hop / body); a generic same-domain inbox
    (``info@``/``contact@``) → ``medium`` as a mailto, else ``low``.
    """
    if not email.same_domain:
        return "low"
    category = classify_localpart(email.address)
    if category == "role":
        return "low"
    if category == "dept":
        return "high" if email.source == "mailto" else "medium"
    return "medium" if email.source == "mailto" else "low"  # generic / other
