"""Detect commercial treatment providers from page text.

The Session 30 validation put precision at ~57%, and the dominant defect was for-profit
treatment facilities: `lahacienda.com`, `michaelshouse.com`, `whitesandstreatment.com`,
`narconon-suncoast.org`. They are real organizations, with real pages, in the right geography,
so every existing gate passes them. But a facility marketing its own treatment services is
competing for the same backlinks we are — it is a competitor, not a prospect.

**Content signals, not a domain list.** A list cannot work here: `txcouncil.com` is the Texas
Council of Community Centers and `whitesandstreatment.com` is a for-profit rehab, so the name
tells you nothing. This reuses the ADR-024 junk-page technique — judge the page by what it
says about itself.

Signals are graded, because the cost of the two errors is not symmetric. Losing a real
coalition is worse than admitting one facility, so:

* a FACILITY term alone is decisive — only a treatment business calls itself a "treatment
  center" or advertises "residential treatment";
* a direct-response CTA alone is NOT, because real nonprofits publish phone numbers and say
  "get help"; two independent CTAs are required.

Deliberately out of scope: aggregator directories that merely *list* a real council
(`rehab.com`, `recovered.org`) and B2B vendors (`behavehealth.com`). Those are different junk
classes and belong to :mod:`platforms`.
"""

import re

# A treatment business describing its own service. Decisive on its own.
_FACILITY_TERMS = (
    "treatment center",
    "treatment centre",
    "rehabilitation center",
    "rehabilitation centre",
    "recovery center",
    "recovery centre",
    "addiction treatment",
    "addiction rehab",
    "drug rehab",
    "alcohol rehab",
    "drug and alcohol treatment",
    "residential treatment",
    "inpatient treatment",
    "outpatient treatment",
    "levels of care",
    "sober living",
    "detox program",
    "detoxification",
    "our rehab",
    "our facility",
    "our treatment",
)

# Direct-response marketing. Real nonprofits do some of this, so two are required.
_CTA_PATTERNS = (
    r"\bcall now\b",
    r"\bcall (?:us )?24/?7\b",
    r"\bcall 24/7\b",
    r"\bget help now\b",
    r"\bneed help now\b",
    r"\bhelp is available now\b",
    r"\bverify your insurance\b",
    r"\binsurance accepted\b",
    r"\bwe accept most insurance\b",
    r"\bfree (?:and )?confidential\b",
    r"\bfree consultation\b",
    r"\bcall\b[^.]{0,24}\b(?:today|now)\b",
    r"\bcall\s*\(?\d[\d\s().-]{7,}\b",
    r"\bstart your recovery today\b",
    r"\bspeak (?:with|to) (?:a|an) (?:admissions|treatment) (?:specialist|advisor)\b",
)

# Two independent CTAs, because one is something a real nonprofit legitimately does.
_CTA_THRESHOLD = 2

_FACILITY_RE = re.compile("|".join(re.escape(t) for t in _FACILITY_TERMS), re.I)
_CTA_RES = tuple(re.compile(p, re.I) for p in _CTA_PATTERNS)


def commercial_signals(text: str) -> tuple[list[str], list[str]]:
    """Return the (facility terms, CTA patterns) found — exposed so a run can explain itself."""
    facility = sorted({m.group(0).lower() for m in _FACILITY_RE.finditer(text)})
    ctas = sorted({r.pattern for r in _CTA_RES if r.search(text)})
    return facility, ctas


def is_commercial_provider(*, title: str, snippet: str, body: str = "") -> bool:
    """True when the text reads as a for-profit treatment facility marketing itself.

    Works on a search result (title + snippet, no fetch required) and on full page text via
    ``body``, so the same rule can run before we spend a fetch and again after.
    """
    text = " ".join(part for part in (title, snippet, body) if part)
    if not text.strip():
        return False
    facility, ctas = commercial_signals(text)
    return bool(facility) or len(ctas) >= _CTA_THRESHOLD
