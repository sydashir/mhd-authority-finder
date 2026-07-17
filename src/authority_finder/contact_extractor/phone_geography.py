"""Phone area-code → US state, to reject a contact phone that contradicts the geo.

Phones encode geography (NANP), so a body-text phone whose area code maps to a
different state than the geo is almost always a third party or an out-of-state
branch scraped off the page (live: ``akleg.gov`` — the Alaska Legislature —
carrying a 559/Fresno-California number). We resolve the number's state through
the maintained ``phonenumbers`` geocoder (libphonenumber's data — authoritative
and already a dependency; better than a hand-kept area-code table, ADR-024) and
drop the phone only on a *confirmed* contradiction. Toll-free numbers carry no
geography and are kept as neutral (never trust-boosted, never rejected).
"""

import phonenumbers
from phonenumbers import geocoder

from authority_finder.contact_extractor.models import PhoneHit
from authority_finder.page_detector.geography import ABBR_TO_SLUG

_STATE_SLUGS = frozenset(ABBR_TO_SLUG.values())
_ABBR_LEN = 2


def phone_state(phone: str) -> str | None:
    """The US state slug a phone's area code maps to, or ``None`` when it can't be
    reliably resolved (toll-free, unparseable, or a non-state region).

    The geocoder returns either a bare state name (``"California"``) or a
    ``"City, ST"`` string (``"Birmingham, AL"``); both are normalised to the
    hyphenated slug used across the codebase (``new-york``).
    """
    try:
        parsed = phonenumbers.parse(phone, "US")
    except phonenumbers.NumberParseException:
        return None
    description = geocoder.description_for_number(parsed, "en")
    if not description:
        return None
    tail = description.rsplit(", ", 1)[-1]
    if len(tail) == _ABBR_LEN and tail.lower() in ABBR_TO_SLUG:
        return ABBR_TO_SLUG[tail.lower()]
    slug = description.lower().replace(" ", "-")
    return slug if slug in _STATE_SLUGS else None


def phone_contradicts_geo(phone: str, geo_state: str) -> bool:
    """True only when ``phone`` reliably maps to a state OTHER than ``geo_state``.

    Unresolvable / toll-free phones return ``False`` (unconfirmable ≠ contradiction)
    — precision over recall.
    """
    state = phone_state(phone)
    return state is not None and state != geo_state


def _e164(hit: PhoneHit) -> str:
    return hit.number or hit.raw


def drop_wrong_geo_phones(phones: list[PhoneHit], geo_state: str) -> list[PhoneHit]:
    """Drop phones whose area code contradicts ``geo_state``; keep order otherwise."""
    return [p for p in phones if not phone_contradicts_geo(_e164(p), geo_state)]


__all__ = ["drop_wrong_geo_phones", "phone_contradicts_geo", "phone_state"]
