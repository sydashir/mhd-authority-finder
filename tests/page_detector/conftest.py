"""Shared builders for page_detector tests. No network anywhere."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from authority_finder.discovery.classify import dedupe_key
from authority_finder.discovery.models import CandidateSite, DomainClass, GeoRef

CALIFORNIA_GEO = GeoRef(
    site_id="mhd",
    url="https://inpatientmentalhealthfinder.com/serving/california/",
    level="state",
    state="california",
)

ORANGE_COUNTY_GEO = GeoRef(
    site_id="mhd",
    url="https://inpatientmentalhealthfinder.com/serving/california/orange-county/",
    level="county",
    state="california",
    county="orange-county",
)


def make_candidate(
    url: str, *, geo: GeoRef = CALIFORNIA_GEO, domain_class: DomainClass = "gov"
) -> CandidateSite:
    return CandidateSite(
        registrable_domain=dedupe_key(url),
        url=HttpUrl(url),
        title="candidate",
        snippet="snippet",
        domain_class=domain_class,
        geo=geo,
        source_queries=["q1"],
        discovered_at=datetime.now(UTC),
    )


def html_page(
    *,
    title: str,
    h1: str = "",
    body: str = "",
    links: tuple[tuple[str, str], ...] = (),
    mailto: bool = False,
    tel: bool = False,
) -> bytes:
    anchor_html = "".join(f'<a href="{href}">{text}</a>' for text, href in links)
    contact_html = ""
    if mailto:
        contact_html += '<a href="mailto:dept@example.gov">Email</a>'
    if tel:
        contact_html += '<a href="tel:+17145551234">Call</a>'
    h1_html = f"<h1>{h1}</h1>" if h1 else ""
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body>{h1_html}<p>{body}</p>{anchor_html}{contact_html}</body></html>"
    ).encode()
