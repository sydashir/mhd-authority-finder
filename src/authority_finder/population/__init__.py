"""Population lookup for a geo via the US Census ACS 5-year API (ADR-008).

Census retired keyless access (May 2026), so a free `CENSUS_API_KEY` is
required; without one, lookups return ``not_found`` rather than blocking — a
missing population never stops a row (golden rule: never fabricate).
"""

from authority_finder.population.models import (
    CensusLevel,
    MatchConfidence,
    PopulationResult,
)

__all__ = ["CensusLevel", "MatchConfidence", "PopulationResult"]
