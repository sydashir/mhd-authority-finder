"""Population lookup models (ADR-008).

Golden rule: never fabricate. ``not_found`` is a valid, honest outcome — a
missing population must never block a row or be guessed. ``confidence``
records how the match was made so the outreach team can trust ``exact`` rows
and eyeball ``fuzzy`` ones.
"""

from typing import Literal

from pydantic import BaseModel

CensusLevel = Literal["state", "county", "place"]
MatchConfidence = Literal["exact", "fuzzy", "not_found"]


class PopulationResult(BaseModel):
    """Population for one geo, with provenance and match confidence."""

    value: int | None
    matched_name: str | None
    geo_level_used: CensusLevel | None
    confidence: MatchConfidence
    source_dataset: str
    note: str = ""
