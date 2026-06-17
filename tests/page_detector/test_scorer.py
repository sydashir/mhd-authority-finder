"""Scorer signal coverage: every signal, wrong-state reject, confidence bands."""

from authority_finder.discovery.models import GeoRef
from authority_finder.fetching import PageContent, PageLink
from authority_finder.page_detector.models import DetectedPage
from authority_finder.page_detector.scorer import (
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    WrongState,
    count_state_mentions,
    is_viable,
    score_page,
)
from tests.page_detector.conftest import CALIFORNIA_GEO, ORANGE_COUNTY_GEO

LONG_BODY = "Community wellbeing programs and public services. " * 20


def make_content(
    *,
    final_url: str = "https://example.gov/services/behavioral-health/",
    title: str = "",
    h1s: list[str] | None = None,
    text: str = "",
    links: list[PageLink] | None = None,
    has_mailto: bool = False,
    has_tel: bool = False,
) -> PageContent:
    return PageContent(
        final_url=final_url,
        title=title,
        h1s=h1s or [],
        meta_description="",
        text_sample=text,
        links=links or [],
        has_mailto=has_mailto,
        has_tel=has_tel,
    )


def _signal_names(page: DetectedPage) -> set[str]:
    return {s.name for s in page.signals}


def test_textbook_county_health_page_scores_high() -> None:
    content = make_content(
        final_url="https://ochealthinfo.gov/services/behavioral-health-resources/",
        title="Behavioral Health Services | Orange County Health Care Agency",
        h1s=["Behavioral Health Services"],
        text="Mental health and substance use treatment for Orange County, California "
        "residents. Crisis support and recovery programs. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=ORANGE_COUNTY_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "high"
    assert page.score >= HIGH_THRESHOLD
    assert page.state_validated
    assert {
        "topic_in_title_h1",
        "topic_in_url_path",
        "resource_marker",
        "target_state_present",
        "locality_present",
        "contact_affordance",
    } <= _signal_names(page)


def test_news_article_penalized() -> None:
    content = make_content(
        final_url="https://example.gov/2026/05/mental-health-funding",
        title="Press Release: New Mental Health Funding",
        text="California announces funding. " + LONG_BODY,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert "news_marker" in _signal_names(page)
    assert page.confidence == "low"


def test_wrong_state_hard_reject() -> None:
    content = make_content(
        title="Orange County Health Department",
        text="Serving Orange County, North Carolina. North Carolina residents can call. "
        "Health services across North Carolina. " + LONG_BODY,
    )
    verdict = score_page(content, geo=ORANGE_COUNTY_GEO)
    assert isinstance(verdict, WrongState)
    assert verdict.dominant_state == "north-carolina"
    assert verdict.mentions >= 2


def test_target_state_present_prevents_wrong_state_reject() -> None:
    content = make_content(
        title="Health Services",
        text="Comparing California with North Carolina and North Carolina again. " + LONG_BODY,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert page.state_validated


def test_single_foreign_state_mention_is_not_a_reject() -> None:
    content = make_content(
        title="Behavioral Health Services",
        text="One mention of Texas only. " + LONG_BODY,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert not page.state_validated


def test_generic_homepage_penalized() -> None:
    links = [PageLink(text=f"Dept {i}", href=f"https://example.gov/d{i}") for i in range(12)]
    content = make_content(
        final_url="https://example.gov/",
        title="Example County",
        text=LONG_BODY,
        links=links,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert "generic_homepage" in _signal_names(page)


def test_thin_content_penalized() -> None:
    content = make_content(title="Mental Health", text="short")
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert "thin_content" in _signal_names(page)


def test_contact_link_fallback_signal() -> None:
    content = make_content(
        title="Mental Health Services",
        text=LONG_BODY,
        links=[PageLink(text="Contact Us", href="https://example.gov/contact")],
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert "contact_link" in _signal_names(page)


def test_confidence_band_medium() -> None:
    content = make_content(
        final_url="https://example.gov/about",
        title="Mental health counseling",
        text="Serving California families. " + LONG_BODY,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert MEDIUM_THRESHOLD <= page.score < HIGH_THRESHOLD
    assert page.confidence == "medium"


def test_viability_floor() -> None:
    content = make_content(
        final_url="https://example.gov/permits", title="Parking Permits", text="short"
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert not is_viable(page)


def test_every_score_decomposes_into_signals() -> None:
    content = make_content(
        title="Behavioral Health Resources",
        text="California crisis services. " + LONG_BODY,
        has_mailto=True,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert page.score == round(sum(s.weight_contribution for s in page.signals), 2)
    assert all(s.detail for s in page.signals)


def test_state_mention_counting_handles_virginia() -> None:
    counts = count_state_mentions("west virginia health and west virginia services")
    assert counts == {"west-virginia": 2}


def test_state_mention_counting_kansas_not_in_arkansas() -> None:
    counts = count_state_mentions("arkansas department of health in arkansas")
    assert counts == {"arkansas": 2}


def test_no_topic_signal_anywhere_caps_confidence_at_low() -> None:
    content = make_content(
        final_url="https://cityofirvine.gov/animal-services",
        title="Animal Services | City of Irvine",
        text="Orange County animal care services in California. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=ORANGE_COUNTY_GEO)
    assert isinstance(page, DetectedPage)
    assert page.score >= MEDIUM_THRESHOLD
    assert page.confidence == "low"


def test_body_only_topic_escapes_the_cap() -> None:
    content = make_content(
        final_url="https://health.maryland.gov/bha/pages/help.aspx",
        title="Pages - HELP",
        h1s=["Get Help"],
        text="Behavioral health crisis services and substance use treatment for Maryland "
        "residents. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(
        content,
        geo=GeoRef(
            site_id="ah",
            url="https://addictionhotline.com/maryland/",
            level="state",
            state="maryland",
        ),
    )
    assert isinstance(page, DetectedPage)
    assert "topic_in_body" in _signal_names(page)
    assert page.confidence == "medium"
