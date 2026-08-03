"""domain_rating must survive the upsert.

ProspectIn carried it and ingest mapped it, but upsert_prospect builds its INSERT from an
explicit column list and the field was missing from BOTH values() and the on-conflict set_ —
so a full states run wrote 1,241 Domain Ratings to the CSV and NULL to every DB row.

It is pipeline-owned data, so unlike the outreach fields (ADR-022) it MUST be in set_ and
refresh on a re-run.
"""

import inspect

from authority_finder.db import repository


class TestUpsertCarriesDomainRating:
    def test_domain_rating_is_in_the_insert_values(self) -> None:
        source = inspect.getsource(repository.upsert_prospect)
        assert "domain_rating=data.domain_rating" in source, (
            "upsert_prospect drops domain_rating — the CSV had it, the DB got NULL"
        )

    def test_domain_rating_refreshes_on_conflict(self) -> None:
        """Pipeline-owned, so a re-run updates it — the opposite of the outreach fields."""
        source = inspect.getsource(repository.upsert_prospect)
        assert '"domain_rating": stmt.excluded.domain_rating' in source

    def test_outreach_fields_are_still_absent_from_set(self) -> None:
        """ADR-022 must not be weakened by this fix."""
        source = inspect.getsource(repository.upsert_prospect)
        for field in ("outreach_status", "outreach_notes", "contacted_at", "outreach_updated_by"):
            assert f'"{field}": stmt.excluded' not in source, f"{field} would clobber user data"
