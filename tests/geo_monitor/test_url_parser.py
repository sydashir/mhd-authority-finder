"""Unit tests for the geo URL parser. Covers MHD + AH patterns, level inference,
state-slug whitelist, URL normalization, query/fragment stripping, and the
AH-specific non-geo rejection cases (/about, /blog, /services, ...).
"""

from datetime import UTC, datetime

import pytest

from authority_finder.geo_monitor.models import GeoLevel
from authority_finder.geo_monitor.sites import AH, MHD
from authority_finder.geo_monitor.url_parser import parse_geo_url

NOW = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("url", "exp_state", "exp_county", "exp_city", "exp_level"),
    [
        (
            "https://inpatientmentalhealthfinder.com/serving/california/",
            "california",
            None,
            None,
            "state",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/california",
            "california",
            None,
            None,
            "state",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/california/los-angeles-county/",
            "california",
            "los-angeles-county",
            None,
            "county",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/california/los-angeles-county/los-angeles/",
            "california",
            "los-angeles-county",
            "los-angeles",
            "city",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/new-hampshire/",
            "new-hampshire",
            None,
            None,
            "state",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/north-carolina/durham-county/durham/",
            "north-carolina",
            "durham-county",
            "durham",
            "city",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/texas/?utm=foo",
            "texas",
            None,
            None,
            "state",
        ),
        (
            "https://inpatientmentalhealthfinder.com/serving/texas/#contact",
            "texas",
            None,
            None,
            "state",
        ),
    ],
)
def test_mhd_geo_urls_parse(
    url: str,
    exp_state: str,
    exp_county: str | None,
    exp_city: str | None,
    exp_level: GeoLevel,
) -> None:
    page = parse_geo_url(url, MHD, now=NOW)
    assert page is not None
    assert page.site_id == "mhd"
    assert page.state == exp_state
    assert page.county == exp_county
    assert page.city == exp_city
    assert page.level == exp_level
    assert page.url.endswith("/")
    assert "?" not in page.url
    assert "#" not in page.url


@pytest.mark.parametrize(
    "url",
    [
        "https://inpatientmentalhealthfinder.com/serving/atlantis/",
        "https://inpatientmentalhealthfinder.com/serving/",
        "https://inpatientmentalhealthfinder.com/serving/california/los-angeles/foo/extra/",
        "https://inpatientmentalhealthfinder.com/about/",
        "https://inpatientmentalhealthfinder.com/california/",
        "https://inpatientmentalhealthfinder.com/serving/CALIFORNIA/",
    ],
)
def test_mhd_non_geo_urls_return_none(url: str) -> None:
    assert parse_geo_url(url, MHD, now=NOW) is None


@pytest.mark.parametrize(
    ("url", "exp_state", "exp_county", "exp_city", "exp_level"),
    [
        (
            "https://addictionhotline.com/california/",
            "california",
            None,
            None,
            "state",
        ),
        (
            "https://addictionhotline.com/california",
            "california",
            None,
            None,
            "state",
        ),
        (
            "https://addictionhotline.com/colorado/denver-county/",
            "colorado",
            "denver-county",
            None,
            "county",
        ),
        (
            "https://addictionhotline.com/washington/king-county/seattle/",
            "washington",
            "king-county",
            "seattle",
            "city",
        ),
        (
            "https://addictionhotline.com/north-carolina/",
            "north-carolina",
            None,
            None,
            "state",
        ),
        (
            "https://addictionhotline.com/new-york/?utm=foo",
            "new-york",
            None,
            None,
            "state",
        ),
        (
            "https://addictionhotline.com/florida/#contact",
            "florida",
            None,
            None,
            "state",
        ),
    ],
)
def test_ah_geo_urls_parse(
    url: str,
    exp_state: str,
    exp_county: str | None,
    exp_city: str | None,
    exp_level: GeoLevel,
) -> None:
    page = parse_geo_url(url, AH, now=NOW)
    assert page is not None
    assert page.site_id == "ah"
    assert page.state == exp_state
    assert page.county == exp_county
    assert page.city == exp_city
    assert page.level == exp_level


@pytest.mark.parametrize(
    "url",
    [
        "https://addictionhotline.com/about/",
        "https://addictionhotline.com/contact/",
        "https://addictionhotline.com/services/",
        "https://addictionhotline.com/blog/",
        "https://addictionhotline.com/treatment-programs/",
        "https://addictionhotline.com/",
        "https://addictionhotline.com/california/county/city/extra/",
        "https://addictionhotline.com/CALIFORNIA/",
    ],
)
def test_ah_non_geo_urls_return_none(url: str) -> None:
    assert parse_geo_url(url, AH, now=NOW) is None


def test_first_seen_is_passed_through() -> None:
    page = parse_geo_url("https://addictionhotline.com/california/", AH, now=NOW)
    assert page is not None
    assert page.first_seen == NOW


def test_url_normalization_adds_trailing_slash() -> None:
    page = parse_geo_url("https://addictionhotline.com/california", AH, now=NOW)
    assert page is not None
    assert page.url == "https://addictionhotline.com/california/"


def test_url_normalization_strips_query_and_fragment() -> None:
    page = parse_geo_url(
        "https://inpatientmentalhealthfinder.com/serving/texas/?a=1&b=2#x", MHD, now=NOW
    )
    assert page is not None
    assert page.url == "https://inpatientmentalhealthfinder.com/serving/texas/"
