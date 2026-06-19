"""Output stage: assemble deliverable rows and write them to CSV or Google Sheets.

CSV is the ``--dry-run`` target (no creds needed); Sheets is the live target.
Both share :data:`OUTPUT_HEADER` / :class:`OutputRow` and dedupe by
(registrable domain, geo).
"""

from authority_finder.output.models import OUTPUT_HEADER, OutputRow, build_row, geo_served_label

__all__ = ["OUTPUT_HEADER", "OutputRow", "build_row", "geo_served_label"]
