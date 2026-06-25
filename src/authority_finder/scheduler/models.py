"""Models for the scheduled incremental runner (ADR-012)."""

from typing import NamedTuple

from pydantic import BaseModel


class RunOutcome(NamedTuple):
    """What one processed batch produced — the seam between orchestration and the pipeline."""

    rows_written: int
    billed_searches: int


class IncrementalRunResult(BaseModel):
    """Result of one incremental run for one site."""

    site_id: str
    new_geos_found: int = 0
    processed: int = 0
    deferred: int = 0
    rows_written: int = 0
    billed_searches: int = 0
    aborted: bool = False
    note: str = ""
