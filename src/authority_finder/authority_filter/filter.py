"""Decide which candidate domains cost Ahrefs units, and which of them survive.

Two rules keep the bill down. ``.gov``/``.edu`` already pass on domain class alone
(ADR-006), so scoring them would be paying for an answer we have. Competitor and federal
domains are excluded everywhere else in the pipeline, so scoring them would be paying to
reject something. Everything else gets one batched Ahrefs lookup.

Sub-threshold domains are dropped but COUNTED, following the instrumentation discipline
of ADR-006 — a silent drop is how ``other`` sat at zero for months without anyone
noticing the queries could never surface it.
"""

from collections.abc import Sequence
from typing import NamedTuple

import tldextract

from authority_finder.authority_filter.ahrefs_client import DomainRating
from authority_finder.authority_filter.platforms import is_platform
from authority_finder.domains import COMPETITOR_DOMAINS, FEDERAL_DOMAINS

# Calibrated against 20 real behavioral-health orgs (ADR-026), not inherited from the
# brief. The brief's 40 rejects ncala.org (34), txcouncil.com (32) and calbhbc.org (29) —
# real STATE-level coalitions, which for a geo-targeted tool are worth more than the
# national bodies that clear 40 easily. The real cliff in the data is 0 vs 29.
DEFAULT_DR_THRESHOLD = 25

_PASS_ON_CLASS = (".gov", ".edu")


class Scoreable(NamedTuple):
    scoreable: list[str]
    skipped_domain_class: list[str]
    skipped_competitor: list[str]
    skipped_federal: list[str]
    skipped_platform: list[str]


class ThresholdOutcome(NamedTuple):
    passed: list[str]
    dropped_below_threshold: dict[str, float]
    dropped_no_data: list[str]

    @property
    def dropped_count(self) -> int:
        return len(self.dropped_below_threshold) + len(self.dropped_no_data)


def registrable(domain: str) -> str:
    """``blog.rehabs.com`` -> ``rehabs.com``; keeps rehabsomething.com distinct (ADR-011)."""
    extracted = tldextract.extract(domain)
    return extracted.top_domain_under_public_suffix.lower() or domain.strip().lower()


def _normalise(target: str) -> str:
    cleaned = target.strip().lower()
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    return cleaned.split("/", 1)[0].removeprefix("www.")


def select_scoreable(domains: Sequence[str]) -> Scoreable:
    """Partition candidates into what needs paying for and what does not.

    Candidates collapse to their registrable domain first, so one organization costs one
    lookup — ``account.texashealth.org`` and ``texashealth.org`` burned two slots before.
    Ordering matters for cost: every skip branch is evaluated BEFORE the Ahrefs call, so a
    platform or a competitor never consumes units.
    """
    scoreable: list[str] = []
    by_class: list[str] = []
    competitor: list[str] = []
    federal: list[str] = []
    platform: list[str] = []
    seen: set[str] = set()

    for host in dict.fromkeys(_normalise(d) for d in domains if d.strip()):
        # Class is decided on the full host: collapsing first would turn hhs.nd.gov into
        # nd.gov and lose which agency was seen.
        if host.endswith(_PASS_ON_CLASS):
            by_class.append(host)
            continue

        root = registrable(host)
        if root in seen:
            continue
        seen.add(root)

        if is_platform(root):
            platform.append(root)
        elif root in COMPETITOR_DOMAINS:
            competitor.append(root)
        elif root in FEDERAL_DOMAINS:
            federal.append(root)
        else:
            scoreable.append(root)

    return Scoreable(
        scoreable=scoreable,
        skipped_domain_class=by_class,
        skipped_competitor=competitor,
        skipped_federal=federal,
        skipped_platform=platform,
    )


def apply_threshold(
    ratings: dict[str, DomainRating], *, threshold: int = DEFAULT_DR_THRESHOLD
) -> ThresholdOutcome:
    """Keep domains at or above ``threshold``; record the rest rather than losing them."""
    passed: list[tuple[str, float]] = []
    below: dict[str, float] = {}
    no_data: list[str] = []

    for domain, rating in ratings.items():
        if rating.dr is None:
            no_data.append(domain)
        elif rating.dr >= threshold:
            passed.append((domain, rating.dr))
        else:
            below[domain] = rating.dr

    passed.sort(key=lambda pair: -pair[1])
    return ThresholdOutcome(
        passed=[domain for domain, _ in passed],
        dropped_below_threshold=below,
        dropped_no_data=sorted(no_data),
    )
