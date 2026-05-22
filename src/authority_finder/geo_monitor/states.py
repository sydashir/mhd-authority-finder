"""Whitelist of US state slugs used to disambiguate geo URLs.

AH's geo URL pattern (``/{state}/...``) matches any top-level path including
``/about``, ``/contact``, ``/services``. Filtering the captured ``state`` group
against this set is the cheapest way to reject non-geo paths without
maintaining a blacklist of marketing pages that grows over time. See ADR-004.

If either site adds DC or US territories in the future, add the corresponding
slug here. The list is intentionally hardcoded (US-only project scope per
``CLAUDE.md``).
"""

from __future__ import annotations

US_STATE_SLUGS: frozenset[str] = frozenset(
    {
        "alabama",
        "alaska",
        "arizona",
        "arkansas",
        "california",
        "colorado",
        "connecticut",
        "delaware",
        "florida",
        "georgia",
        "hawaii",
        "idaho",
        "illinois",
        "indiana",
        "iowa",
        "kansas",
        "kentucky",
        "louisiana",
        "maine",
        "maryland",
        "massachusetts",
        "michigan",
        "minnesota",
        "mississippi",
        "missouri",
        "montana",
        "nebraska",
        "nevada",
        "new-hampshire",
        "new-jersey",
        "new-mexico",
        "new-york",
        "north-carolina",
        "north-dakota",
        "ohio",
        "oklahoma",
        "oregon",
        "pennsylvania",
        "rhode-island",
        "south-carolina",
        "south-dakota",
        "tennessee",
        "texas",
        "utah",
        "vermont",
        "virginia",
        "washington",
        "west-virginia",
        "wisconsin",
        "wyoming",
    }
)
