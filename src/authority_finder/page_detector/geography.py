"""Derive a candidate domain's US state from its ``.gov``/``.us`` domain — but ONLY
where it's reliable (ADR-020). Everything ambiguous returns ``None`` so the scorer
falls back to page-text evidence.

Reliable signals:
- a state-portal registrable domain / subdomain (``dol.ny.gov`` → ``ny.gov`` → NY;
  ``hhs.texas.gov`` → ``texas.gov`` → TX);
- a ``county{2-letter-abbr}`` suffix (``wyomingcounty**ny**.gov`` → NY) — a county
  domain always encodes its OWN state, and the "county" anchor makes the abbr safe;
- a ``{...}.{abbr}.us`` municipal suffix (``co.orange.ca.us`` → CA).

Deliberately NOT derived (false-positive risk): bare ``{city}{abbr}.gov``
(``napa.gov`` ends in ``pa`` but is California), full-state-name suffix
(``portwashington.gov`` is NY/WI, not Washington state), any ``.edu``, cryptic
acronyms (``dconc.gov`` = Durham County NC). These fall back to text.
"""

import re
from urllib.parse import urlparse

from authority_finder.discovery.classify import registrable_domain

ABBR_TO_SLUG: dict[str, str] = {
    "al": "alabama",
    "ak": "alaska",
    "az": "arizona",
    "ar": "arkansas",
    "ca": "california",
    "co": "colorado",
    "ct": "connecticut",
    "de": "delaware",
    "fl": "florida",
    "ga": "georgia",
    "hi": "hawaii",
    "id": "idaho",
    "il": "illinois",
    "in": "indiana",
    "ia": "iowa",
    "ks": "kansas",
    "ky": "kentucky",
    "la": "louisiana",
    "me": "maine",
    "md": "maryland",
    "ma": "massachusetts",
    "mi": "michigan",
    "mn": "minnesota",
    "ms": "mississippi",
    "mo": "missouri",
    "mt": "montana",
    "ne": "nebraska",
    "nv": "nevada",
    "nh": "new-hampshire",
    "nj": "new-jersey",
    "nm": "new-mexico",
    "ny": "new-york",
    "nc": "north-carolina",
    "nd": "north-dakota",
    "oh": "ohio",
    "ok": "oklahoma",
    "or": "oregon",
    "pa": "pennsylvania",
    "ri": "rhode-island",
    "sc": "south-carolina",
    "sd": "south-dakota",
    "tn": "tennessee",
    "tx": "texas",
    "ut": "utah",
    "vt": "vermont",
    "va": "virginia",
    "wa": "washington",
    "wv": "west-virginia",
    "wi": "wisconsin",
    "wy": "wyoming",
}
# Full-name portals (texas.gov, maryland.gov, …) — EXACT registrable label only, never a suffix.
_NAME_TO_SLUG: dict[str, str] = {slug.replace("-", ""): slug for slug in ABBR_TO_SLUG.values()}
_NAME_TO_SLUG["newyork"] = "new-york"

_COUNTY_ABBR = re.compile(r"county([a-z]{2})$")
_MIN_US_HOST_PARTS = 3  # host.abbr.us — the smallest {sub}.{abbr}.us shape we can read


def _gov_state(label: str) -> str | None:
    """State slug from a ``.gov`` registrable label (portal or county{abbr}), else ``None``."""
    if label in ABBR_TO_SLUG:
        return ABBR_TO_SLUG[label]
    if label in _NAME_TO_SLUG:
        return _NAME_TO_SLUG[label]
    match = _COUNTY_ABBR.search(label)
    return ABBR_TO_SLUG.get(match.group(1)) if match is not None else None


def candidate_state(url: str) -> str | None:
    """The candidate's US state slug if its domain reliably encodes it, else ``None``.

    ``None`` means "not reliably derivable" — the scorer then relies on page-text evidence.
    """
    host = urlparse(url if "://" in url else f"http://{url}").netloc.split(":")[0].lower()
    if not host:
        return None
    parts = host.split(".")
    tld = parts[-1]
    if tld == "us":
        # Municipal .us encodes the state in the suffix: co.orange.ca.us → ca.
        return ABBR_TO_SLUG.get(parts[-2]) if len(parts) >= _MIN_US_HOST_PARTS else None
    if tld != "gov":
        return None
    return _gov_state(registrable_domain(url).split(".")[0])
