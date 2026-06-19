"""CSV output writer — the ``--dry-run`` target (no credentials needed).

Dedupes by (registrable domain, geo) and sorts so the most valuable prospects
sit at the top: by geo, then detection confidence (high→low), then population
(desc; unknown last).
"""

import csv
from pathlib import Path

from authority_finder.output.models import OUTPUT_HEADER, OutputRow

_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}


def _sort_key(row: OutputRow) -> tuple[str, int, int]:
    pop_desc = -(row.population if row.population is not None else -1)
    return (row.geo_served, _CONFIDENCE_RANK.get(row.confidence, 3), pop_desc)


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
