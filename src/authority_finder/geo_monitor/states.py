"""Whitelist of US state slugs used to disambiguate geo URLs.

AH's geo URL pattern (``/{state}/...``) matches any top-level path including
``/about``, ``/contact``, ``/services``. Filtering the captured ``state`` group
against this set is the cheapest way to reject non-geo paths without
maintaining a blacklist of marketing pages that grows over time. See ADR-004.

DC and the US territories are included: MHD publishes ``/serving/`` pages for
them. The list is intentionally hardcoded (US-only project scope per
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
        # DC and the US territories. MHD publishes /serving/ pages for all of these, so they
        # are in scope; the unparsed-URL instrumentation (ADR-031) is what surfaced them —
        # before that they returned None and vanished silently.
        "district-of-columbia",
        # MHD's own URL says "colombia" (the country) rather than "columbia". Accepting both
        # is deliberate: it is their published URL, and losing a real page to someone else's
        # typo is worse than carrying a second slug.
        "district-of-colombia",
        "puerto-rico",
        "guam",
        "virgin-islands",
        "northern-mariana-islands",
        "american-samoa",
    }
)
