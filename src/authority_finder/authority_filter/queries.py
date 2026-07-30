"""Unrestricted per-geo query templates for authority organizations. No I/O.

These deliberately carry NO ``site:`` filter, and that is the entire reason component 3
could not work before. Discovery's templates are scoped with
``(site:.gov OR site:.edu)``, so they can only ever return government and university
domains — which is why ADR-006's ``other`` classification bucket was instrumented,
counted, and came back zero every single run. It was not that no such organizations
exist; it was that the query could not express them.

The themes target the organization types the brief names — state coalitions, behavioral
health associations, recovery councils — rather than the departments discovery already
finds. Results are non-.gov/.edu by construction, so they are the domains worth spending
Ahrefs units on.
"""

from authority_finder.discovery.queries import county_display, slug_to_display
from authority_finder.geo_monitor.models import GeoPage

STATE_QUERIES = (
    "{state} mental health coalition",
    "{state} behavioral health association",
    "{state} addiction recovery organization",
    "{state} substance abuse council",
)

COUNTY_QUERIES = (
    '"{county} County" {state} mental health coalition',
    '"{county} County" {state} behavioral health association',
    '"{county} County" {state} substance abuse council',
)

CITY_QUERIES = (
    '"{city}" {state} mental health coalition',
    '"{city}" {state} addiction recovery organization',
    '"{city}" {state} behavioral health council',
)


def build_authority_queries(geo: GeoPage) -> list[str]:
    """Unrestricted queries for ``geo``, most specific level only."""
    state = slug_to_display(geo.state)

    if geo.level == "city" and geo.city:
        templates = CITY_QUERIES
        values = {"state": state, "city": slug_to_display(geo.city)}
    elif geo.level == "county" and geo.county:
        templates = COUNTY_QUERIES
        values = {"state": state, "county": county_display(geo.county)}
    else:
        templates = STATE_QUERIES
        values = {"state": state}

    return list(dict.fromkeys(template.format(**values) for template in templates))
