"""CSV output writer — the ``--dry-run`` target (no credentials needed).

Dedupes by (registrable domain, geo) and sorts so the most valuable prospects
sit at the top: rows whose org **already links to a competing directory** lead (ADR-011
detects this; an org that has listed a directory before has proven it will), then by
**contact trust** (high→low), then population (desc; unknown last), then geo.

At 622 rows / 72 geos a geo-first sort scattered the high-trust rows alphabetically and
buried the value (S24); ranking proven directory-listers above them (S32) puts the rows
outreach is most likely to convert at the very top.
"""

import csv
from pathlib import Path

from authority_finder.output.models import OUTPUT_HEADER, OutputRow

_TRUST_RANK = {"high": 0, "medium": 1, "low": 2}
# How "no competitor links" is written in the sheet; not evidence of anything.
_NO_LINKS = {"", "—", "-"}


def links_to_a_competitor(row: OutputRow) -> bool:
    """True when this org already links out to one of the 16 competing directories."""
    return row.competitor_links.strip() not in _NO_LINKS


def _sort_key(row: OutputRow) -> tuple[int, int, int, str]:
    pop_desc = -(row.population if row.population is not None else -1)
    # Primary signal: an org that already lists a competing directory has DEMONSTRATED it
    # will list one. That beats an inferred property like contact trust or Domain Rating,
    # so those rows lead the sheet (S32, on top of ADR-011's detection).
    return (
        0 if links_to_a_competitor(row) else 1,
        _TRUST_RANK.get(row.contact_trust, 3),
        pop_desc,
        row.geo_served,
    )


def dedupe_and_sort(rows: list[OutputRow]) -> list[OutputRow]:
    """Sort best-first, then keep the first (best) row per (domain, geo)."""
    ordered = sorted(rows, key=_sort_key)
    seen: set[tuple[str, str]] = set()
    out: list[OutputRow] = []
    for row in ordered:
        if row.dedupe_key in seen:
            continue
        seen.add(row.dedupe_key)
        out.append(row)
    return out


def write_csv(rows: list[OutputRow], path: Path) -> int:
    """Write deduped, sorted rows to ``path`` with the canonical header. Returns count."""
    final = dedupe_and_sort(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_HEADER)
        writer.writerows(row.cells() for row in final)
    return len(final)
