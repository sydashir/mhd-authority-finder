"""Free .gov domain lookup from the vendored CISA registry (ADR-029).

Discovery has been paying Google to answer "which .gov sites exist in this county?" — but
CISA publishes the complete list of US .gov domains for free. So for `.gov` that question is
a **lookup, not a search**, and the paid queries collapse to the `.org`/`.com` authority
source alone.

Verified against the live 589-row dataset before building: all 266 `.gov` domains it ever
found are present here — 208 exactly, 58 as their parent domain (`hhs.nd.gov` → `nd.gov`).
Zero missing. The parent-domain case is fine: `page_detector`'s bounded crawl already finds
the department page from a root, which is exactly what the paid search was buying.

The file is vendored, not fetched at runtime — a scheduled run must not depend on an external
host being up. Refresh with:

    curl -sL https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv \
      -o data/gov_domains.csv

Matching notes drawn from the real data: a County row's ``City`` field is the county SEAT
(``pinellas.gov`` is City=Clearwater), so counties match on ``Organization name``; city rows
match on ``City``.
"""

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from authority_finder.page_detector.geography import ABBR_TO_SLUG

REGISTRY_PATH = Path("data/gov_domains.csv")

_STATE_TYPES = {"State or territory"}
_COUNTY_TYPES = {"County"}
_CITY_TYPES = {"City"}

_SLUG_TO_ABBR: dict[str, str] = {slug: abbr for abbr, slug in ABBR_TO_SLUG.items()}
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Words that carry no identity — dropped so "Orange County" matches an org named "Orange".
_NOISE = {"county", "city", "of", "the", "town", "village", "borough", "parish"}


class GovDomain(NamedTuple):
    domain: str
    kind: str
    organization: str
    city: str
    state: str


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_NON_ALNUM.sub(" ", value.lower()).split()) - _NOISE


def slug_tokens(slug: str) -> frozenset[str]:
    """``orange-county`` → {"orange"}; ``st-louis`` → {"st", "louis"}."""
    return _tokens(slug.replace("-", " "))


@lru_cache(maxsize=1)
def load_registry(path: str = str(REGISTRY_PATH)) -> tuple[GovDomain, ...]:
    """The vendored registry, parsed once."""
    file = Path(path)
    if not file.is_file():
        return ()
    with file.open(newline="") as handle:
        return tuple(
            GovDomain(
                domain=row["Domain name"].strip().lower(),
                kind=row["Domain type"].strip(),
                organization=row["Organization name"].strip(),
                city=row["City"].strip(),
                state=row["State"].strip().upper(),
            )
            for row in csv.DictReader(handle)
            if row.get("Domain name")
        )


def domains_for_geo(
    *, state: str, county: str | None = None, city: str | None = None
) -> list[GovDomain]:
    """.gov domains registered to this place, most specific level first.

    ``state`` is our slug (``north-carolina``). A city geo also returns its county's and
    state's domains, because a county health department is a legitimate prospect for a city
    page — the narrower rows simply lead.
    """
    abbr = _SLUG_TO_ABBR.get(state.lower())
    abbr = abbr.upper() if abbr else None  # registry stores AL, our map yields al
    if abbr is None:
        return []
    in_state = [row for row in load_registry() if row.state == abbr]

    out: list[GovDomain] = []
    if city:
        wanted = slug_tokens(city)
        out += [r for r in in_state if r.kind in _CITY_TYPES and _tokens(r.city) & wanted]
    if county:
        wanted = slug_tokens(county)
        # County rows carry the county name in the ORGANISATION, not the City column, which
        # holds the county seat (pinellas.gov -> City=Clearwater).
        out += [r for r in in_state if r.kind in _COUNTY_TYPES and _tokens(r.organization) & wanted]
    out += [r for r in in_state if r.kind in _STATE_TYPES]

    seen: set[str] = set()
    unique: list[GovDomain] = []
    for row in out:
        if row.domain not in seen:
            seen.add(row.domain)
            unique.append(row)
    return unique
