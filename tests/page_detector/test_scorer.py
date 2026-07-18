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


WYOMING_GEO = GeoRef(
    site_id="ah",
    url="https://addictionhotline.com/wyoming/",
    level="state",
    state="wyoming",
)

ALABAMA_GEO = GeoRef(
    site_id="ah",
    url="https://addictionhotline.com/alabama/",
    level="state",
    state="alabama",
)


def test_news_subdomain_capped_to_low() -> None:
    # ADR-024 bucket C: a news/press subdomain is never the department page — cap it to low
    # even when the article is topical and geo-confirmed (news.calstatela.edu scored HIGH).
    content = make_content(
        final_url="https://news.calstatela.edu/2026/04/06/cal-state-la-mental-health-services/",
        title="Cal State LA Expands Mental Health Services",
        h1s=["Mental Health Services"],
        text="Counseling and crisis support for students in California. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "low"
    assert "junk_page_type" in _signal_names(page)


def test_press_release_headline_slug_capped_to_low() -> None:
    # The alabamaag.gov defect: a press release with a long headline slug (no /news/ section)
    # scored HIGH. A headline-length slug is a press release, not a resource page.
    slug = "attorney-general-and-health-officer-announce-issuance-of-opioid-council-report"
    content = make_content(
        final_url=f"https://www.alabamaag.gov/{slug}/",
        title="Opioid Council Report",
        h1s=["Mental Health and Substance Use"],
        text="Alabama behavioral health and treatment resources. " + LONG_BODY,
        has_mailto=True,
    )
    page = score_page(content, geo=ALABAMA_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "low"
    assert "junk_page_type" in _signal_names(page)


def test_business_directory_capped_to_low() -> None:
    content = make_content(
        final_url="https://www.hooveralabama.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=30",
        title="Business Directory",
        h1s=["Mental Health Services"],
        text="Alabama mental health provider services directory. " + LONG_BODY,
    )
    page = score_page(content, geo=ALABAMA_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "low"
    assert "junk_page_type" in _signal_names(page)


def test_department_page_with_long_slug_not_capped() -> None:
    # ucop.edu FP (ADR-024 audit): a real /departments/ CAPS page whose long slug IS the
    # spelled-out department name, not a headline — the long-slug heuristic must not cap it.
    url = (
        "https://ucop.edu/uc-health/departments/"
        "uc-student-health-and-counseling-shcs-and-counseling-and-psychological-services-caps.html"
    )
    content = make_content(
        final_url=url,
        title="Student Health and Counseling Services",
        h1s=["Counseling and Psychological Services"],
        text="Mental health and counseling services across California campuses. " + LONG_BODY,
        has_mailto=True,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert "junk_page_type" not in _signal_names(page)
    assert page.confidence != "low"


def test_normal_resource_page_not_flagged_junk() -> None:
    # Regression: a short-slug department page must NOT be flagged as junk.
    content = make_content(
        final_url="https://ochealthinfo.gov/services/behavioral-health/",
        title="Behavioral Health Services",
        h1s=["Behavioral Health Services"],
        text="Mental health resources for Orange County, California residents. " + LONG_BODY,
        has_mailto=True,
    )
    page = score_page(content, geo=ORANGE_COUNTY_GEO)
    assert isinstance(page, DetectedPage)
    assert "junk_page_type" not in _signal_names(page)


def test_domain_contradicts_target_is_hard_rejected() -> None:
    # The killer S19 case: wyomingcountyny.gov is Wyoming COUNTY, New York. Its page says
    # "Wyoming" constantly (the county's name), so text-only passed it — the domain (…ny.gov)
    # is the only truth. Domain contradiction must hard-reject regardless of text.
    content = make_content(
        final_url="https://wyomingcountyny.gov/health/",
        title="Wyoming County Health Department",
        text="Wyoming County services for Wyoming County residents. " + LONG_BODY,
    )
    verdict = score_page(content, geo=WYOMING_GEO)
    assert isinstance(verdict, WrongState)
    assert verdict.dominant_state == "new-york"


def test_unconfirmable_target_state_demoted_to_low() -> None:
    # An .edu absent from the Scorecard snapshot can't be geolocated, and the page never names
    # Wyoming — neither domain nor text confirms the target, so it must not ship as verified.
    content = make_content(
        final_url="https://regionalcollege.edu/student-health/",
        title="Student Mental Health and Counseling Services",
        text="Counseling and psychological services for students. Crisis support. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=WYOMING_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "low"
    assert "geo_unconfirmed" in {s.name for s in page.signals}


def test_edu_wrong_state_hard_rejected() -> None:
    # ADR-024 bucket A: cornell.edu is a New York university — under a Wyoming geo it must
    # HARD-REJECT (not merely demote), same as a wrong-state .gov domain. The page text is
    # deliberately generic so only the domain proves the contradiction.
    content = make_content(
        final_url="https://cornell.edu/student-health/",
        title="Student Mental Health and Counseling Services",
        text="Counseling and psychological services for students. Crisis support. " + LONG_BODY,
        has_mailto=True,
    )
    verdict = score_page(content, geo=WYOMING_GEO)
    assert isinstance(verdict, WrongState)
    assert verdict.dominant_state == "new-york"


def test_multi_campus_edu_confirmed_in_a_campus_state() -> None:
    # midwestern.edu has both an Illinois and an Arizona campus — under Arizona it must be
    # geo-confirmed (not rejected, not demoted), the multi-campus precision case.
    arizona = GeoRef(
        site_id="ah", url="https://addictionhotline.com/arizona/", level="state", state="arizona"
    )
    content = make_content(
        final_url="https://midwestern.edu/programs/behavioral-health/",
        title="Behavioral Health Programs",
        text="Mental health and counseling services. Crisis support. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=arizona)
    assert isinstance(page, DetectedPage)
    assert page.confidence != "low"
    assert page.state_validated


def test_domain_confirmed_candidate_not_demoted() -> None:
    # cdph.ca.gov confirms California by domain even without the word "California" on the page —
    # a state agency must not be demoted just because its page doesn't spell out the state.
    content = make_content(
        final_url="https://cdph.ca.gov/programs/behavioral-health/",
        title="Behavioral Health Services",
        text="Mental health and substance use treatment programs. Crisis support. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence != "low"
    assert page.state_validated


def test_target_named_but_not_dominant_is_demoted() -> None:
    # A page that names the target once but is dominated by another state (a national/multi-state
    # org) is weak evidence — it must not pass as confirmed just for mentioning the target.
    content = make_content(
        final_url="https://nationalcounseling.edu/programs/",
        title="Counseling and Mental Health Programs",
        text="Serving Wyoming, plus California, California, California residents. " + LONG_BODY,
        has_mailto=True,
    )
    page = score_page(content, geo=WYOMING_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "low"


def test_domain_confirmed_survives_other_state_in_text() -> None:
    # A confirmed-California domain is a California org even if its page discusses another state —
    # the domain is authoritative, so the text-based wrong-state reject must be suppressed.
    content = make_content(
        final_url="https://cdph.ca.gov/programs/",
        title="Behavioral Health Services",
        text="Comparing programs with North Carolina and North Carolina again. " + LONG_BODY,
    )
    page = score_page(content, geo=CALIFORNIA_GEO)
    assert isinstance(page, DetectedPage)


def test_cryptic_out_of_state_gov_demoted() -> None:
    # Bucket 3: dconc.gov is Durham County NC; 'dconc' can't be derived, and a topical page with
    # no California/Orange-County context must be demoted, not shipped for an Orange County geo.
    content = make_content(
        final_url="https://dconc.gov/behavioral-health/",
        title="Behavioral Health Services",
        text="Mental health and substance use programs. Crisis and recovery support. " + LONG_BODY,
        has_tel=True,
    )
    page = score_page(content, geo=ORANGE_COUNTY_GEO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "low"
    assert "geo_unconfirmed" in {s.name for s in page.signals}


def test_locality_in_text_confirms_out_of_domain_edu() -> None:
    # A .edu we can't geolocate but that names the target locality IS geo-confirmed — naming
    # "Long Beach" must not be demoted just because the domain carries no derivable state.
    long_beach = GeoRef(
        site_id="mhd",
        url="https://inpatientmentalhealthfinder.com/serving/california/los-angeles/long-beach/",
        level="city",
        state="california",
        county="los-angeles",
        city="long-beach",
    )
    content = make_content(
        final_url="https://regionalcollege.edu/counseling/",
        title="Counseling and Psychological Services",
        text="Serving students in Long Beach. Mental health and crisis support. " + LONG_BODY,
        has_mailto=True,
        has_tel=True,
    )
    page = score_page(content, geo=long_beach)
    assert isinstance(page, DetectedPage)
    assert page.confidence != "low"


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
