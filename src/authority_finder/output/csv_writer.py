"""CSV output writer — the ``--dry-run`` target (no credentials needed).

Dedupes by (registrable domain, geo) and sorts so the most valuable prospects
sit at the top: by **contact trust** (high→low) first, then population (desc;
unknown last), then geo. At 622 rows / 72 geos a geo-first sort scattered the
high-trust rows alphabetically and buried the value (S24) — trust-first puts the
rows outreach can actually act on at the top of the sheet.
"""

import csv
from pathlib import Path

from authority_finder.output.models import OUTPUT_HEADER, OutputRow

_TRUST_RANK = {"high": 0, "medium": 1, "low": 2}


def _sort_key(row: OutputRow) -> tuple[int, int, str]:
    pop_desc = -(row.population if row.population is not None else -1)
    return (_TRUST_RANK.get(row.contact_trust, 3), pop_desc, row.geo_served)


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
