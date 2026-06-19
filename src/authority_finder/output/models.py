"""Output row schema — the deliverable's columns (ADR-008).

Columns follow `docs/brief.md` order exactly, plus an 11th internal
``Confidence`` column so the outreach team can sort by detection confidence
(the feasibility doc's flagging system, surfaced in the sheet). Every field is
a string in the row (CSV/Sheets are string grids); missing data → empty cell,
never fabricated.
"""

from datetime import datetime

from pydantic import BaseModel

from authority_finder.contact_extractor.models import ExtractionOutcome
from authority_finder.discovery.queries import county_display, slug_to_display
from authority_finder.population.models import PopulationResult

OUTPUT_HEADER: list[str] = [
    "Website",
    "Specific Page",
    "Email",
    "Phone",
    "Organization Description",
    "Geo Served",
    "Population",
    "Competitor Links",
    "Source Tag",
    "Date Added",
    "Confidence",
]

_SOURCE_TAGS = {"mhd": "MHD", "ah": "AH"}
_MAX_DESCRIPTION = 240


class OutputRow(BaseModel):
    """One outreach prospect row. ``dedupe_key`` is (registrable domain, geo url)."""

    website: str
    specific_page: str
    email: str
    phone: str
    organization_description: str
    geo_served: str
    population: int | None
    competitor_links: str
    source_tag: str
    date_added: str
    confidence: str

    @property
    def dedupe_key(self) -> tuple[str, str]:
        return (self.website, self.geo_served)

    def cells(self) -> list[str]:
        """The row as 11 string cells, in :data:`OUTPUT_HEADER` order."""
        return [
            self.website,
            self.specific_page,
            self.email,
            self.phone,
            self.organization_description,
            self.geo_served,
            "" if self.population is None else str(self.population),
            self.competitor_links,
            self.source_tag,
            self.date_added,
            self.confidence,
        ]


def geo_served_label(*, level: str, state: str, county: str | None, city: str | None) -> str:
    """Human geo label: 'Maryland' / 'Orange County, California' / 'Newport Beach, California'."""
    state_name = slug_to_display(state)
    if level == "county" and county:
        return f"{county_display(county)} County, {state_name}"
    if level == "city" and city:
        return f"{slug_to_display(city)}, {state_name}"
    return state_name


def build_row(
    outcome: ExtractionOutcome,
    *,
    population: PopulationResult,
    now: datetime,
) -> OutputRow:
    """Assemble one :class:`OutputRow` from the chained per-candidate outputs.

    Every missing piece degrades to an empty cell — never crashes, never fabricates.
    """
    candidate = outcome.candidate
    geo = candidate.geo
    contacts = outcome.contacts
    description = (candidate.snippet or candidate.title or "").strip()[:_MAX_DESCRIPTION]

    return OutputRow(
        website=candidate.registrable_domain,
        specific_page=outcome.page_url,
        email=contacts.best_email or "",
        phone=contacts.best_phone or "",
        organization_description=description,
        geo_served=geo_served_label(
            level=geo.level, state=geo.state, county=geo.county, city=geo.city
        ),
        population=population.value,
        competitor_links="—",  # Phase 2 (link_checker); not yet computed
        source_tag=_SOURCE_TAGS.get(geo.site_id, geo.site_id.upper()),
        date_added=now.date().isoformat(),
        confidence=outcome.page_confidence,
    )
