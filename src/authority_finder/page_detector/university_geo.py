"""University ``.edu`` domain → US state(s), closing the ADR-020 wrong-state gap.

ADR-020 could geolocate ``.gov``/``.us`` domains but deliberately deferred ``.edu``
(a bare ``.edu`` label doesn't encode its state). At full scale that was the single
largest content defect — universities filed under the wrong geo (``vaughn.edu``, a
New York college, under Alaska). This resolves a ``.edu`` registrable domain to the
set of states where it operates, using a vendored snapshot of the federal **College
Scorecard** institution directory (``data/university_states.csv``: domain → state
slugs, 90% corpus coverage).

Multi-campus universities map to a *set* of states (``midwestern.edu`` → AZ + IL) so a
row is wrong-state only when the geo is in *none* of them — precision over recall. A
domain not in the snapshot returns ``None`` and the scorer falls back to page-text
evidence honestly, rather than asserting a state we can't prove.
"""

import csv
from functools import cache
from pathlib import Path

from authority_finder.discovery.classify import registrable_domain

_DATA_PATH = Path(__file__).parent / "data" / "university_states.csv"

# Physical branch campuses the College Scorecard single-institution row misses, verified
# against each university's own site (ADR-024 adversarial audit). Unioned onto the CSV states
# so a genuine out-of-main-state campus is not wrong-state-rejected for the geo it serves.
_BRANCH_CAMPUS_STATES: dict[str, frozenset[str]] = {
    "wbu.edu": frozenset({"hawaii"}),  # Wayland Baptist — Kapolei HI campus + HI military bases
    "widener.edu": frozenset({"delaware"}),  # Widener Delaware Law School, Wilmington DE
}


@cache
def _states_by_domain() -> dict[str, frozenset[str]]:
    with _DATA_PATH.open(encoding="utf-8") as handle:
        states = {
            row["domain"]: frozenset(row["states"].split(";"))
            for row in csv.DictReader(handle)
            if row.get("domain") and row.get("states")
        }
    for domain, extra in _BRANCH_CAMPUS_STATES.items():
        states[domain] = states.get(domain, frozenset()) | extra
    return states


def university_states(url: str) -> frozenset[str] | None:
    """State slugs a ``.edu`` domain operates in, or ``None`` if not a known ``.edu``.

    ``None`` means "not derivable" — a non-``.edu`` domain or one absent from the
    Scorecard snapshot — so the scorer relies on page-text evidence instead.
    """
    domain = registrable_domain(url)
    if not domain.endswith(".edu"):
        return None
    return _states_by_domain().get(domain)
