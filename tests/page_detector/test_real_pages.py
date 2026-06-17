"""Regression tests against real HTML captured during the Session 5 live run.

These pin parse + score behavior on actual .gov/.edu markup (CMS noise,
megamenus, obfuscated contact links) so scorer/parser changes that would
break real-world detection fail here first. Fixtures fetched 2026-06-13.
"""

from pathlib import Path

from authority_finder.discovery.models import GeoRef
from authority_finder.fetching import parse_html
from authority_finder.page_detector.models import DetectedPage
from authority_finder.page_detector.scorer import score_page

FIXTURES = Path(__file__).parent / "fixtures"

MARYLAND = GeoRef(
    site_id="ah", url="https://addictionhotline.com/maryland/", level="state", state="maryland"
)
COLORADO = GeoRef(
    site_id="ah", url="https://addictionhotline.com/colorado/", level="state", state="colorado"
)
ORANGE_COUNTY = GeoRef(
    site_id="mhd",
    url="https://inpatientmentalhealthfinder.com/serving/california/orange-county/",
    level="county",
    state="california",
    county="orange-county",
)


def test_montgomery_county_mh_resources_scores_high() -> None:
    body = (FIXTURES / "montgomerycountymd_mh_resources.html").read_bytes()
    content = parse_html(
        body,
        final_url="https://www.montgomerycountymd.gov/office-human-resources/mental-health-resources-public-safety",
    )
    page = score_page(content, geo=MARYLAND)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "high"
    assert page.state_validated
    names = {s.name for s in page.signals}
    assert "topic_in_title_h1" in names
    assert "topic_in_url_path" in names


def test_colorado_college_counseling_scores_high() -> None:
    body = (FIXTURES / "coloradocollege_mh_resources.html").read_bytes()
    content = parse_html(
        body,
        final_url="https://www.coloradocollege.edu/offices/counseling/mental-health-resources.html",
    )
    page = score_page(content, geo=COLORADO)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "high"
    assert page.state_validated


def test_oc_supervisor_mh_resources_detects_locality() -> None:
    body = (FIXTURES / "bos4_oc_mental_health.html").read_bytes()
    content = parse_html(body, final_url="https://bos4.oc.gov/mental-health-resources")
    page = score_page(content, geo=ORANGE_COUNTY)
    assert isinstance(page, DetectedPage)
    assert page.confidence == "high"
    names = {s.name for s in page.signals}
    assert "locality_present" in names
    assert "target_state_present" in names
