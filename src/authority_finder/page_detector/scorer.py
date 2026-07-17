"""Page scoring: named signals → score → confidence band. Pure functions.

Rule-based and explainable by design (ADR-006): every score decomposes into
:class:`PageSignal` entries the outreach team can read and argue with.
Weights and thresholds are module constants, tuned against the Session 4/5
live corpus.

Wrong-state hard rejection: only full state names are counted (2-letter codes
collide with English words — "in", "or", "me"). "Virginia" matches inside
"West Virginia", so the West Virginia count is subtracted from Virginia's.
A known residual: "washington" also matches Washington County / Washington
D.C. mentions — tolerated because rejection additionally requires the target
state to be completely absent.
"""

import re
from typing import NamedTuple
from urllib.parse import urlparse

from authority_finder.discovery.models import GeoRef
from authority_finder.discovery.queries import county_display, slug_to_display
from authority_finder.fetching import PageContent
from authority_finder.geo_monitor.states import US_STATE_SLUGS
from authority_finder.page_detector.geography import candidate_state
from authority_finder.page_detector.models import Confidence, DetectedPage, PageSignal
from authority_finder.page_detector.university_geo import university_states

TOPIC_KEYWORDS = (
    "mental health",
    "behavioral health",
    "substance",
    "addiction",
    "treatment",
    "counseling",
    "crisis",
    "recovery",
    "probation",
)
RESOURCE_MARKERS = ("resources", "services", "get help", "find help")
NEWS_TITLE_MARKERS = ("press release", "news release", "newsroom", "in the news")
DATE_PATH_RE = re.compile(r"/(19|20)\d{2}(/\d{1,2})?(/|$)")

W_TOPIC_TITLE = 3.0
W_TOPIC_PATH = 2.0
W_TOPIC_BODY = 0.5
W_RESOURCE_MARKER = 2.0
W_STATE_PRESENT = 2.0
W_LOCALITY_PRESENT = 1.5
W_CONTACT_AFFORDANCE = 1.5
W_CONTACT_LINK = 0.5
W_NEWS_PAGE = -3.0
W_GENERIC_HOMEPAGE = -1.5
W_THIN_CONTENT = -2.0

HIGH_THRESHOLD = 8.0
MEDIUM_THRESHOLD = 4.5
VIABILITY_FLOOR = 1.5

THIN_CONTENT_CHARS = 500
HOMEPAGE_MIN_LINKS = 10
WRONG_STATE_MIN_COUNT = 2

_STATE_NAMES: dict[str, str] = {slug: slug_to_display(slug).lower() for slug in US_STATE_SLUGS}
_STATE_PATTERNS: dict[str, re.Pattern[str]] = {
    slug: re.compile(rf"\b{re.escape(name)}\b") for slug, name in _STATE_NAMES.items()
}


class WrongState(NamedTuple):
    """Hard-reject verdict: another state dominates and the target is absent."""

    dominant_state: str
    mentions: int


def count_state_mentions(text: str) -> dict[str, int]:
    """Occurrences of each US state's full name in lowercase ``text``."""
    counts: dict[str, int] = {}
    for slug, pattern in _STATE_PATTERNS.items():
        n = len(pattern.findall(text))
        if n:
            counts[slug] = n
    if "west-virginia" in counts and "virginia" in counts:
        counts["virginia"] -= counts["west-virginia"]
        if counts["virginia"] <= 0:
            del counts["virginia"]
    return counts


def _locality_names(geo: GeoRef) -> list[str]:
    names: list[str] = []
    if geo.level == "county" and geo.county:
        names.append(county_display(geo.county).lower())
    if geo.level == "city" and geo.city:
        names.append(slug_to_display(geo.city).lower())
        if geo.county:
            names.append(county_display(geo.county).lower())
    return names


def _contact_signal(content: PageContent) -> PageSignal | None:
    if content.has_mailto or content.has_tel:
        kinds = [
            k
            for k, present in (("mailto", content.has_mailto), ("tel", content.has_tel))
            if present
        ]
        return PageSignal(
            name="contact_affordance",
            weight_contribution=W_CONTACT_AFFORDANCE,
            detail="/".join(kinds),
        )
    if any("contact" in (link.text + " " + link.href).lower() for link in content.links):
        return PageSignal(
            name="contact_link", weight_contribution=W_CONTACT_LINK, detail="internal contact link"
        )
    return None


def score_page(content: PageContent, *, geo: GeoRef) -> DetectedPage | WrongState:
    """Score one fetched page for one geo, or return a :class:`WrongState` verdict."""
    title_h1 = " ".join([content.title, *content.h1s]).lower()
    path = urlparse(content.final_url).path.lower()
    searchable = " ".join([title_h1, content.meta_description.lower(), content.text_sample.lower()])

    state_counts = count_state_mentions(searchable)
    target_count = state_counts.get(geo.state, 0)
    # The candidate DOMAIN's state (where reliably derivable) is authoritative — it beats page
    # text, which can be actively misleading (wyomingcountyny.gov's page is full of "Wyoming",
    # but the domain proves it's a New York county). ADR-020.
    cand_state = candidate_state(content.final_url)
    domain_confirms = cand_state == geo.state
    if cand_state is not None and not domain_confirms:
        return WrongState(dominant_state=cand_state, mentions=0)
    # .edu domains carry no state in the label, so ADR-020 deferred them; the College
    # Scorecard snapshot closes that gap (ADR-024). A multi-campus university confirms the
    # geo if it's ANY of its campus states; a university operating in none of them is a
    # wrong-state hard reject, exactly like a contradicting .gov domain.
    uni_states = university_states(content.final_url)
    if uni_states is not None:
        if geo.state in uni_states:
            domain_confirms = True
        else:
            return WrongState(dominant_state=sorted(uni_states)[0], mentions=0)
    if not domain_confirms and target_count == 0 and state_counts:
        dominant, mentions = max(state_counts.items(), key=lambda kv: kv[1])
        if mentions >= WRONG_STATE_MIN_COUNT:
            return WrongState(dominant_state=dominant, mentions=mentions)

    topic_title = [k for k in TOPIC_KEYWORDS if k in title_h1]
    topic_path = [k for k in TOPIC_KEYWORDS if k.replace(" ", "-") in path or k in path]
    topic_body = [k for k in TOPIC_KEYWORDS if k in searchable]
    resource = [m for m in RESOURCE_MARKERS if m in title_h1 or m.replace(" ", "-") in path]
    matched_locality = [n for n in _locality_names(geo) if n and n in searchable]

    candidate_signals: list[tuple[bool, str, float, str]] = [
        (bool(topic_title), "topic_in_title_h1", W_TOPIC_TITLE, ", ".join(topic_title)),
        (bool(topic_path), "topic_in_url_path", W_TOPIC_PATH, ", ".join(topic_path)),
        (
            bool(topic_body) and not topic_title and not topic_path,
            "topic_in_body",
            W_TOPIC_BODY,
            ", ".join(topic_body[:5]),
        ),
        (bool(resource), "resource_marker", W_RESOURCE_MARKER, ", ".join(resource)),
        (
            target_count > 0,
            "target_state_present",
            W_STATE_PRESENT,
            f"{_STATE_NAMES[geo.state]} x{target_count}",
        ),
        (
            bool(matched_locality),
            "locality_present",
            W_LOCALITY_PRESENT,
            ", ".join(matched_locality),
        ),
        (
            bool(DATE_PATH_RE.search(path)) or any(m in title_h1 for m in NEWS_TITLE_MARKERS),
            "news_marker",
            W_NEWS_PAGE,
            "dated path or press/news title",
        ),
        (
            path in ("", "/") and len(content.links) >= HOMEPAGE_MIN_LINKS,
            "generic_homepage",
            W_GENERIC_HOMEPAGE,
            f"{len(content.links)} links on root path",
        ),
        (
            len(content.text_sample) < THIN_CONTENT_CHARS,
            "thin_content",
            W_THIN_CONTENT,
            f"{len(content.text_sample)} chars",
        ),
    ]
    signals: list[PageSignal] = [
        PageSignal(name=name, weight_contribution=weight, detail=detail)
        for hit, name, weight, detail in candidate_signals
        if hit
    ]
    contact = _contact_signal(content)
    if contact is not None:
        signals.append(contact)

    score = round(sum(s.weight_contribution for s in signals), 2)
    confidence: Confidence = (
        "high" if score >= HIGH_THRESHOLD else "medium" if score >= MEDIUM_THRESHOLD else "low"
    )
    # No topic relevance ANYWHERE — title, path, or body (live case: an
    # "Animal Services" page cleared medium on services+locality+contact
    # alone) → flag for review, never promote. Body-only topic (live case:
    # health.maryland.gov/bha titled just "Get Help") escapes the cap.
    if not topic_title and not topic_path and not topic_body:
        confidence = "low"
    # Geo-confirmation gate (ADR-020): a candidate whose target geo is confirmed by NEITHER the
    # domain, NOR strong text (target state present AND not out-mentioned by another state — a
    # national/multi-state page naming the target once is weak), NOR (county/city) the locality is
    # unverifiable — cap it to low / flag it rather than ship a possibly out-of-state prospect.
    other_state_max = max((c for s, c in state_counts.items() if s != geo.state), default=0)
    text_confirms = target_count > 0 and target_count >= other_state_max
    if not (domain_confirms or text_confirms or matched_locality):
        confidence = "low"
        signals.append(
            PageSignal(
                name="geo_unconfirmed",
                weight_contribution=0.0,
                detail="target state/locality not confirmed by domain or page text",
            )
        )
    return DetectedPage(
        url=content.final_url,
        score=score,
        confidence=confidence,
        signals=signals,
        state_validated=target_count > 0 or domain_confirms,
    )


def is_viable(page: DetectedPage) -> bool:
    """A page below the viability floor isn't worth a sheet row at all."""
    return page.score >= VIABILITY_FLOOR
