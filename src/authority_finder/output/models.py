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
from authority_finder.output.provenance import contact_source_label, contact_trust
from authority_finder.population.models import PopulationResult

OUTPUT_HEADER: list[str] = [
    "Website",
    "Specific Page",
    "Email",
    "Phone",
    "Contact Source",  # provenance of the contact (ADR-009)
    "Contact Trust",  # can outreach trust this contact (≠ page Confidence)
    "Organization Description",
    "Geo Served",
    "Population",
    "Competitor Links",
    "Source Tag",
    "Date Added",
    "Confidence",
    # APPEND-ONLY. The live master tab is read positionally by _existing_keys (Website and
    # Geo Served), so a new column may only go on the end (ADR-027).
    "Domain Rating",
    # Blank means "same page as Specific Page" — so blank needs no explanation, and a value
    # only appears when it tells the reader something they could not otherwise know.
    "Competitor Links Found On",
]

_SOURCE_TAGS = {"mhd": "MHD", "ah": "AH"}
_MAX_DESCRIPTION = 240


class OutputRow(BaseModel):
    """One outreach prospect row. ``dedupe_key`` is (registrable domain, geo url)."""

    website: str
    specific_page: str
    email: str
    phone: str
    contact_source: str
    contact_trust: str
    organization_description: str
    geo_served: str
    population: int | None
    competitor_links: str
    source_tag: str
    date_added: str
    confidence: str
    # Ahrefs DR for authority-sourced rows. None for .gov/.edu, which are deliberately never
    # scored (ADR-027) — blank means "not measured"; 0 would be a false claim of no authority.
    domain_rating: float | None = None
    # Where the competitor links actually appear, when that is NOT the contact page. The
    # check covers the detected page plus one resources hop (ADR-011), so links frequently
    # live on a sub-page; showing only the contact URL made a correct row look wrong.
    competitor_links_found_on: str = ""

    @property
    def dedupe_key(self) -> tuple[str, str]:
        return (self.website, self.geo_served)

    def cells(self) -> list[str]:
        """The row as string cells, in :data:`OUTPUT_HEADER` order."""
        return [
            self.website,
            self.specific_page,
            self.email,
            self.phone,
            self.contact_source,
            self.contact_trust,
            self.organization_description,
            self.geo_served,
            "" if self.population is None else str(self.population),
            self.competitor_links,
            self.source_tag,
            self.date_added,
            self.confidence,
            "" if self.domain_rating is None else f"{self.domain_rating:g}",
            self.competitor_links_found_on,
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
    competitor_links: str = "—",
    domain_rating: float | None = None,
    competitor_links_found_on: str = "",
) -> OutputRow:
    """Assemble one :class:`OutputRow` from the chained per-candidate outputs.

    ``competitor_links`` is the pre-formatted cell from the link checker (component 6),
    e.g. ``"samhsa.gov; recovery.com"``; ``"—"`` when none / not checked. Every missing
    piece degrades to an empty cell — never crashes, never fabricates.
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
        contact_source=contact_source_label(contacts),
        contact_trust=contact_trust(contacts),
        organization_description=description,
        geo_served=geo_served_label(
            level=geo.level, state=geo.state, county=geo.county, city=geo.city
        ),
        population=population.value,
        competitor_links=competitor_links,
        source_tag=_SOURCE_TAGS.get(geo.site_id, geo.site_id.upper()),
        date_added=now.date().isoformat(),
        confidence=outcome.page_confidence,
        domain_rating=domain_rating,
        competitor_links_found_on=competitor_links_found_on,
    )
