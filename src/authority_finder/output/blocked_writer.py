"""Write the blocked-candidate list: real orgs a human should visit by hand.

A candidate behind a CAPTCHA or a hard 403 is not a failure to hide — it is a prospect the
tool cannot reach but a person can. ncala.org, the brief's own named example, is exactly
this case. Handing the client a named list turns a silent loss into an action item.
"""

import csv
from pathlib import Path
from typing import NamedTuple

from authority_finder.page_detector.blocked import BlockReason, classify_block, is_blocked
from authority_finder.page_detector.models import DetectionResult

BLOCKED_HEADER = ["Website", "Geo Served", "Block Reason", "Source Page"]


class BlockedCandidate(NamedTuple):
    website: str
    geo_served: str
    reason: str
    source_page: str


def collect_blocked(results: list[DetectionResult]) -> list[BlockedCandidate]:
    """Blocked candidates across a run, deduped by (domain, geo), best-known reason kept."""
    seen: dict[tuple[str, str], BlockedCandidate] = {}
    for result in results:
        for outcome in result.outcomes:
            if outcome.status != "fetch_failed" or not outcome.block_reason:
                continue
            reason = BlockReason(outcome.block_reason)
            if not is_blocked(reason):
                continue
            geo = result.geo.url
            key = (outcome.candidate.registrable_domain, geo)
            seen.setdefault(
                key,
                BlockedCandidate(
                    website=outcome.candidate.registrable_domain,
                    geo_served=geo,
                    reason=reason.value,
                    source_page=str(outcome.candidate.url),
                ),
            )
    return sorted(seen.values())


def write_blocked(rows: list[BlockedCandidate], path: Path | str) -> int:
    """Write the list to ``path``. Returns the count."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(BLOCKED_HEADER)
        for row in rows:
            writer.writerow([row.website, row.geo_served, row.reason, row.source_page])
    return len(rows)


__all__ = [
    "BLOCKED_HEADER",
    "BlockedCandidate",
    "classify_block",
    "collect_blocked",
    "write_blocked",
]
