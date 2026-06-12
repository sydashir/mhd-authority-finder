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
from authority_finder.geo_monitor.states import US_STATE_SLUGS
from authority_finder.page_detector.fetcher import PageContent
from authority_finder.page_detector.models import Confidence, DetectedPage, PageSignal

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
    if target_count == 0 and state_counts:
        dominant, mentions = max(state_counts.items(), key=lambda kv: kv[1])
        if mentions >= WRONG_STATE_MIN_COUNT:
            return WrongState(dominant_state=dominant, mentions=mentions)

    signals: list[PageSignal] = []

    def add(name: str, weight: float, detail: str) -> None:
        signals.append(PageSignal(name=name, weight_contribution=weight, detail=detail))

    topic_title = [k for k in TOPIC_KEYWORDS if k in title_h1]
    if topic_title:
        add("topic_in_title_h1", W_TOPIC_TITLE, ", ".join(topic_title))

    topic_path = [k for k in TOPIC_KEYWORDS if k.replace(" ", "-") in path or k in path]
    if topic_path:
        add("topic_in_url_path", W_TOPIC_PATH, ", ".join(topic_path))

    resource = [m for m in RESOURCE_MARKERS if m in title_h1 or m.replace(" ", "-") in path]
    if resource:
        add("resource_marker", W_RESOURCE_MARKER, ", ".join(resource))

    if target_count > 0:
        add("target_state_present", W_STATE_PRESENT, f"{_STATE_NAMES[geo.state]} x{target_count}")

    matched_locality = [n for n in _locality_names(geo) if n and n in searchable]
    if matched_locality:
        add("locality_present", W_LOCALITY_PRESENT, ", ".join(matched_locality))

    contact = _contact_signal(content)
    if contact is not None:
        signals.append(contact)

    if DATE_PATH_RE.search(path) or any(m in title_h1 for m in NEWS_TITLE_MARKERS):
        add("news_marker", W_NEWS_PAGE, "dated path or press/news title")

    if path in ("", "/") and len(content.links) >= HOMEPAGE_MIN_LINKS:
        add("generic_homepage", W_GENERIC_HOMEPAGE, f"{len(content.links)} links on root path")

    if len(content.text_sample) < THIN_CONTENT_CHARS:
        add("thin_content", W_THIN_CONTENT, f"{len(content.text_sample)} chars")

    score = round(sum(s.weight_contribution for s in signals), 2)
    confidence: Confidence = (
        "high" if score >= HIGH_THRESHOLD else "medium" if score >= MEDIUM_THRESHOLD else "low"
    )
    return DetectedPage(
        url=content.final_url,
        score=score,
        confidence=confidence,
        signals=signals,
        state_validated=target_count > 0,
    )


def is_viable(page: DetectedPage) -> bool:
    """A page below the viability floor isn't worth a sheet row at all."""
    return page.score >= VIABILITY_FLOOR
