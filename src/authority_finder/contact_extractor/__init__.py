"""Contact-info extractor (ADR-003, ADR-007).

For each detected department/resource page, extracts a public email and phone
direct from the page (mailto/tel links first, then vetted body-text patterns),
falling back to one same-domain contact page when the page yields no email.
Direct scraping only — no Hunter/Apollo. Rows without contact info are flagged
(``partial``/``none``), never discarded.
"""

from authority_finder.contact_extractor.models import (
    ContactSet,
    EmailHit,
    ExtractionOutcome,
    ExtractionResult,
    ExtractionStatus,
    PhoneHit,
)

__all__ = [
    "ContactSet",
    "EmailHit",
    "ExtractionOutcome",
    "ExtractionResult",
    "ExtractionStatus",
    "PhoneHit",
]
