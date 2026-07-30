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

# Cryptic .gov county/city domains whose state the rules above CAN'T parse, verified by hand
# (QA audit, ADR-025). Kept tiny + evidence-cited — each one lets the scorer hard-reject a
# domain served to the wrong state (dconc.gov = Durham County NC slipped through to CA geos).
_KNOWN_GOV_STATES: dict[str, str] = {
    "dconc.gov": "north-carolina",  # Durham County, North Carolina
}


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
        # ADR-028: component 3's authority candidates are mostly .org/.com, so the .gov-only
        # rule left the majority of new candidates with no domain-level geo check at all —
        # mhaorangeny.com (Orange County NEW YORK) reached output under Orange County CA.
        # .edu stays excluded: its geography comes from the College Scorecard set (ADR-024).
        if tld == "edu":
            return None
        return _org_state(registrable_domain(url))
    registrable = registrable_domain(url)
    if registrable in _KNOWN_GOV_STATES:
        return _KNOWN_GOV_STATES[registrable]
    return _gov_state(registrable.split(".")[0])


# Two-letter codes that are safe to read as a bare domain SUFFIX. Most codes are common
# English word-endings and would assert a wrong state — which causes a hard reject, i.e.
# deletes a real prospect. Excluded for exactly that reason, with the trap in brackets:
#   il [txcouncIL]  or [vendOR]  in [informatION]  me [medicaRE-like]  ct [produCT]
#   ia [medIA]  ut [aboUT]  ak [breAK]  nd [fuND]  ks [plurals]  ri [safaRI]  ok  co  la
#   ma  pa  hi  de  id  al  ca  va  wa  ga  mo  ne  ar  mt
# What remains are codes that essentially never terminate an English word.
_SAFE_SUFFIX_ABBRS = frozenset(
    {"ny", "nc", "tx", "nj", "nv", "wy", "sc", "vt", "wv", "mn", "az", "nm", "nh", "sd"}
)
_MIN_STEM = 2  # a code needs a real stem in front of it, so "ny.org" alone asserts nothing

_LABEL_SPLIT = re.compile(r"[^a-z]+")


def _name_state(label: str) -> str | None:
    """A single unambiguous full state name inside the label, else ``None``.

    Two different state names (``montana-themed-cafe-in-ohio``) means the domain is not
    telling us where the org is, so it asserts nothing.
    """
    found = {slug for name, slug in _NAME_TO_SLUG.items() if name in label}
    return next(iter(found)) if len(found) == 1 else None


def _suffix_abbr_state(label: str) -> str | None:
    """A safe-listed two-letter code at the very END of the label, else ``None``."""
    stem, code = label[:-2], label[-2:]
    if len(stem) < _MIN_STEM or code not in _SAFE_SUFFIX_ABBRS:
        return None
    return ABBR_TO_SLUG.get(code)


def _org_state(registrable: str) -> str | None:
    """State from a non-.gov registrable domain, only where genuinely derivable (ADR-028)."""
    label = _LABEL_SPLIT.sub("", registrable.rsplit(".", 1)[0])
    return _name_state(label) or _suffix_abbr_state(label)
