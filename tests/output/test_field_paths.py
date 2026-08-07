"""Every OutputRow field must have a populated path all the way to the client.

Three times now a field has been captured by the pipeline and silently dropped before the
client ever saw it:

  1. domain_rating  — build_row accepted it but never assigned it; later, upsert_prospect
                      built its INSERT from an explicit column list that omitted it, so the
                      CSV had 1,241 values and every DB row had NULL.
  2. found_on_url   — CompetitorLink recorded which page the links were on, and nothing read
                      it. The client reported a "false positive" that was actually correct
                      detection with invisible provenance.
  3. (the next one) — caught here instead of by the client.

These tests are deliberately structural rather than value-based: they assert the WIRING
exists, so a new field cannot be added to OutputRow and quietly go nowhere.
"""

import inspect

from authority_finder.db import ingest, repository
from authority_finder.output.models import OUTPUT_HEADER, OutputRow, build_row

# Fields assembled inside build_row from the outcome itself rather than passed in.
_DERIVED = {
    "website",
    "specific_page",
    "email",
    "phone",
    "contact_source",
    "contact_trust",
    "organization_description",
    "geo_served",
    "population",
    "source_tag",
    "date_added",
    "confidence",
}


def _fields() -> list[str]:
    return list(OutputRow.model_fields)


class TestHeaderMatchesModel:
    def test_every_field_has_a_header_column(self) -> None:
        """Except the handful deliberately held back from the sheet, which still reach the DB."""
        published = [f for f in _fields() if f not in OutputRow.SHEET_EXCLUDED_FIELDS]
        assert len(published) == len(OUTPUT_HEADER), (
            f"OutputRow has {len(published)} publishable fields but OUTPUT_HEADER has "
            f"{len(OUTPUT_HEADER)} columns — a field would never reach the sheet"
        )

    def test_an_excluded_field_must_still_reach_the_database(self) -> None:
        """Opting out of the sheet is not a licence to go nowhere — the DB tests below cover
        every field, excluded or not, so a hidden field cannot become a silent dead end."""
        for field in OutputRow.SHEET_EXCLUDED_FIELDS:
            assert field in _fields()
            assert field not in _DERIVED

    def test_cells_emits_one_value_per_header_column(self) -> None:
        row = OutputRow(
            website="x.edu",
            specific_page="https://x.edu/",
            email="",
            phone="",
            contact_source="",
            contact_trust="low",
            organization_description="",
            geo_served="California",
            population=None,
            competitor_links="—",
            source_tag="AH",
            date_added="2026-08-04",
            confidence="low",
        )
        assert len(row.cells()) == len(OUTPUT_HEADER)


class TestBuildRowAssignsWhatItAccepts:
    """The domain_rating bug: a parameter accepted and never assigned."""

    def test_every_build_row_parameter_is_assigned_to_the_row(self) -> None:
        source = inspect.getsource(build_row)
        params = [
            p
            for p in inspect.signature(build_row).parameters
            if p not in {"outcome", "population", "now"}
        ]
        for param in params:
            assert f"{param}={param}" in source, (
                f"build_row accepts {param!r} but never assigns it — it would be "
                "silently discarded, exactly like domain_rating was"
            )


class TestPipelineOwnedFieldsReachTheDatabase:
    """The upsert bug: ProspectIn carried the field, the SQL dropped it."""

    def test_every_non_derived_field_is_in_the_upsert(self) -> None:
        source = inspect.getsource(repository.upsert_prospect)
        for field in _fields():
            if field in _DERIVED:
                continue
            assert f"{field}=data.{field}" in source, (
                f"{field!r} is not in upsert_prospect's INSERT values — the CSV would "
                "carry it and the database would hold NULL"
            )

    def test_every_non_derived_field_refreshes_on_conflict(self) -> None:
        """Pipeline-owned data must update on a re-run; outreach fields must NOT."""
        source = inspect.getsource(repository.upsert_prospect)
        for field in _fields():
            if field in _DERIVED:
                continue
            assert f'"{field}": stmt.excluded.{field}' in source, (
                f"{field!r} would go stale on a re-run"
            )

    def test_ingest_maps_every_field(self) -> None:
        source = inspect.getsource(ingest)
        for field in _fields():
            assert f"{field}=row.{field}" in source or field in _DERIVED, (
                f"{field!r} is not mapped from OutputRow in ingest"
            )


class TestOutreachFieldsStayProtected:
    """ADR-022 must not be weakened by any of the above."""

    def test_user_owned_fields_are_absent_from_the_conflict_set(self) -> None:
        source = inspect.getsource(repository.upsert_prospect)
        for field in (
            "outreach_status",
            "outreach_notes",
            "contacted_at",
            "outreach_updated_by",
        ):
            assert f'"{field}": stmt.excluded' not in source, (
                f"{field} would clobber what the team entered"
            )
