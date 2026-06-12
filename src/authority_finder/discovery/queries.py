"""Per-level SerpAPI query templates and the pure query builder. No I/O.

Query THEMES (health department, mental health resources, probation, student
counseling/health) are locked to the client's brief; only wording is tunable.

Slug→display is best-effort per-word title-casing: ``"north-carolina"`` →
``"North Carolina"``, ``"st-louis"`` → ``"St Louis"`` (no period, and names
like "McAllen" or "DuPage" come out as "Mcallen" / "Dupage"). Google matching
is case-insensitive so this is cosmetic, not a correctness issue.
"""

from authority_finder.geo_monitor.models import GeoPage

STATE_QUERIES = (
    "{state} mental health resources (site:.gov OR site:.edu)",
    "{state} department of health behavioral health site:.gov",
    "{state} substance abuse services site:.gov",
    "{state} university student counseling site:.edu",
)

COUNTY_QUERIES = (
    '"{county} County" {state} health department site:.gov',
    '"{county} County" {state} mental health resources (site:.gov OR site:.edu)',
    '"{county} County" {state} probation department site:.gov',
)

CITY_QUERIES = (
    '"{city}" {state} health department site:.gov',
    '"{city}" {state} mental health resources (site:.gov OR site:.edu)',
    '"{city}" {state} probation OR "community services" site:.gov',
    '"{city}" {state} university student health site:.edu',
)


def slug_to_display(slug: str) -> str:
    """Convert a URL slug to a display name: ``"north-carolina"`` → ``"North Carolina"``."""
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def county_display(slug: str) -> str:
    """County display name *without* a trailing "County".

    MHD county slugs are inconsistent — ``"orange-county"`` but ``"los-angeles"``
    — and the county templates append the word themselves, so a raw conversion
    would produce ``"Orange County County"``.
    """
    return slug_to_display(slug).removesuffix(" County")


def build_queries(geo: GeoPage) -> list[str]:
    """Build the per-level search queries for one geo."""
    state = slug_to_display(geo.state)
    if geo.level == "state":
        return [t.format(state=state) for t in STATE_QUERIES]
    if geo.level == "county":
        if geo.county is None:
            raise ValueError(f"county-level geo without county slug: {geo.url}")
        county = county_display(geo.county)
        return [t.format(county=county, state=state) for t in COUNTY_QUERIES]
    if geo.city is None:
        raise ValueError(f"city-level geo without city slug: {geo.url}")
    city = slug_to_display(geo.city)
    return [t.format(city=city, state=state) for t in CITY_QUERIES]
