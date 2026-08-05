"""Blank phone numbers that several unrelated organisations share (ADR-035).

The curated hotline list in ``contact_extractor.extract`` blocks the lines we already know.
It cannot block the ones we don't: it is hand-written, and the S48 audit found it holding
three numbers while ten were live in the client's sheet.

This is the half that needs no list. Mined from the delivered data, ``+18009898137`` sat on
SEVEN different organisations across SEVEN states. One number cannot be the switchboard of
seven organisations in seven states, so it is a shared referral line and belongs to none of
them — no curation required to know that.

Keyed on distinct STATE rather than row count, deliberately. Two agencies inside one state
genuinely do share a switchboard (``dss.sd.gov`` and ``sdbehavioralhealth.gov``), and blanking
those would delete real contacts to fix a smaller problem.

Runs over a whole run's rows, so a single-geo scheduled tick has nothing to compare and the
curated list remains the only guard there. That is a known limit, not an oversight.
"""

from collections import defaultdict

from authority_finder.output.models import OutputRow


def _state_of(geo_served: str) -> str:
    """``Orange County, California`` and ``California`` are the same state, not two."""
    return geo_served.rsplit(",", 1)[-1].strip().lower()


def blank_shared_phones(rows: list[OutputRow]) -> tuple[list[OutputRow], int]:
    """Blank each phone shared by DIFFERENT organisations in 2+ states. Returns (rows, blanked).

    Both conditions are required. A national body legitimately serves many states from its own
    switchboard (``mhanational.org`` spans 16 geos), so states alone would delete a real number;
    and two agencies in one state genuinely share a line, so organisations alone would too.
    """
    states_by_phone: dict[str, set[str]] = defaultdict(set)
    sites_by_phone: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.phone:
            states_by_phone[row.phone].add(_state_of(row.geo_served))
            sites_by_phone[row.phone].add(row.website.strip().lower())

    shared = {
        phone
        for phone, states in states_by_phone.items()
        if len(states) > 1 and len(sites_by_phone[phone]) > 1
    }
    if not shared:
        return rows, 0

    out: list[OutputRow] = []
    blanked = 0
    for row in rows:
        if row.phone in shared:
            out.append(row.model_copy(update={"phone": ""}))
            blanked += 1
        else:
            out.append(row)
    return out, blanked
