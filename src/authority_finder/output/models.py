"""Output row schema — the deliverable's columns (ADR-008).

Columns follow `docs/brief.md` order exactly, plus an 11th internal
``Confidence`` column so the outreach team can sort by detection confidence
(the feasibility doc's flagging system, surfaced in the sheet). Every field is
a string in the row (CSV/Sheets are string grids); missing data → empty cell,
never fabricated.
"""

from datetime import datetime
from typing import ClassVar

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
    # Where the CONTACT came from, when that is not the same page as Specific Page. Specific
    # Page is the page the client clicks, so it must be the page holding the competitor links
    # (ADR-036); this column keeps the contact page, which is still needed for outreach.
    "Contact Found On",
    # The wider link classes (ADR-039). These are SEPARATE columns rather than a widening of
    # Competitor Links, because that column is contractual — it means the brief's 16, and a
    # delivered column must not change meaning under the client.
    "Addiction Directories",
    "Mental Health Directories",
    "Support Groups",
    "Support Groups Found On",
]

# What a link-class cell says when the check ran and found nothing. Matches how
# Competitor Links has always read, so the new columns are legible on sight.
_NONE_FOUND = "—"

_SOURCE_TAGS = {"mhd": "MHD", "ah": "AH"}


def source_tag_for(site_ids: set[str]) -> str:
    """The Source Tag for a prospect whose geography is published by ``site_ids`` (ADR-037).

    The tag records which directories the prospect SERVES, not which run last touched the row.
    Most state-level prospects serve both, and the two-value enum forced them to claim one —
    so filtering the sheet by AH returned 22 rows out of 2,237 and read as "AH was never built".

    Raises rather than defaulting: an unattributable row must be visible, not quietly MHD.
    """
    if not site_ids:
        raise ValueError("no site: cannot attribute a prospect to a directory")
    unknown = site_ids - _SOURCE_TAGS.keys()
    if unknown:
        raise ValueError(f"unknown site id(s): {sorted(unknown)}")
    if len(site_ids) > 1:
        return "Both"
    return _SOURCE_TAGS[next(iter(site_ids))]


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
    # The page the email/phone came from, when Specific Page is a different page. Blank when
    # one page did both jobs, so a value only appears when it tells the reader something.
    contact_found_on: str = ""
    # Semicolon-joined domains per link class (ADR-039). "—" when the check ran and found
    # none, matching how Competitor Links already reads.
    addiction_directories: str = _NONE_FOUND
    mental_health_directories: str = _NONE_FOUND
    support_groups: str = _NONE_FOUND
    # Blank rather than "—": this is provenance, so an empty cell means "nothing to point at",
    # while a dash would read as a finding of its own.
    support_groups_found_on: str = ""
    # EVERY outbound domain the checked pages linked to, semicolon-joined. Persisted but never
    # published — hundreds of domains per row would be noise in the client's sheet. It exists
    # so that widening a seed list later is a database pass rather than another crawl.
    outbound_domains: str = ""

    # Fields that are deliberately DB-only. Everything else must have a header column, which
    # is what stops a captured field from silently going nowhere (see tests/output).
    SHEET_EXCLUDED_FIELDS: ClassVar[frozenset[str]] = frozenset({"outbound_domains"})

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
            self.contact_found_on,
            self.addiction_directories,
            self.mental_health_directories,
            self.support_groups,
            self.support_groups_found_on,
        ]


def choose_pages(*, detected_page: str, link_pages: list[str]) -> tuple[str, str]:
    """Pick (Specific Page, Contact Found On) for one row.

    The client opens Specific Page. If the competitor links live on a different page than the
    one the contact came from, THAT is the page he needs, so it takes the column (ADR-036).
    The contact page is not lost — it moves to its own column, because the email and phone
    genuinely came from there and outreach still needs it.

    Returns a blank second element when one page did both jobs, so a value in the sheet always
    means something the reader could not otherwise work out.
    """
    for page in link_pages:
        if page and page != detected_page:
            return page, detected_page
    return detected_page, ""


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
    contact_found_on: str = "",
    specific_page: str = "",
    source_tag: str = "",
    addiction_directories: str = _NONE_FOUND,
    mental_health_directories: str = _NONE_FOUND,
    support_groups: str = _NONE_FOUND,
    support_groups_found_on: str = "",
    outbound_domains: str = "",
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
        specific_page=specific_page or outcome.page_url,
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
        source_tag=source_tag or _SOURCE_TAGS.get(geo.site_id, geo.site_id.upper()),
        date_added=now.date().isoformat(),
        confidence=outcome.page_confidence,
        domain_rating=domain_rating,
        contact_found_on=contact_found_on,
        addiction_directories=addiction_directories,
        mental_health_directories=mental_health_directories,
        support_groups=support_groups,
        support_groups_found_on=support_groups_found_on,
        outbound_domains=outbound_domains,
    )
