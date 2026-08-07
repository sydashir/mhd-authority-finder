"""Saved filter views giving the MHD and AH views without a second tab (ADR-042).

The feasibility doc promised separate MHD and AH tabs. Measured against the live sitemaps,
MHD publishes 6,299 geographies and AH 56, of which 54 overlap — the two exceptions being
`palos-verdes` and `port-hueneme`, which MHD publishes as cities and AH as counties. AH's
coverage is therefore a subset of MHD's, and a genuine AH tab would hold 2,099 rows that all
already appear on the MHD tab, putting 1,965 organisations on two surfaces at once. Two reps
working two tabs would both see the same prospect as uncontacted.

A filter view delivers the same two views with no duplicated rows, no second outreach surface,
and no second set of shrink/header guards. Each viewer's filter is private to them, so one
person filtering does not change what anyone else sees.

Criteria are expressed as "hide the OTHER site's exclusive tag" rather than "show these two
values". That is what keeps the views correct as the data moves: today there are no AH-only
rows at all, and if one appears tomorrow it shows up in the AH view without anyone editing a
filter. An explicit allow-list would silently drop any tag value nobody thought to list.
"""

from dataclasses import dataclass
from typing import Any

from authority_finder.output.models import OUTPUT_HEADER

_SOURCE_TAG_COLUMN = OUTPUT_HEADER.index("Source Tag")


@dataclass(frozen=True)
class FilterViewSpec:
    """One saved view: a title and the tag values it hides."""

    title: str
    hidden_tags: tuple[str, ...]


# Titles are part of the contract with the sheet: sync deletes by title before re-adding, so
# renaming one here would orphan the old view rather than replace it.
FILTER_VIEWS: tuple[FilterViewSpec, ...] = (
    FilterViewSpec(title="MHD prospects", hidden_tags=("AH",)),
    FilterViewSpec(title="AH prospects", hidden_tags=("MHD",)),
)


def build_filter_view_specs(*, sheet_id: int, row_count: int) -> list[dict[str, Any]]:
    """Sheets API filter-view objects for the Prospects tab.

    The range spans the header row so the view is filterable by column name, and every column
    in :data:`OUTPUT_HEADER` — derived, never a literal, because a hard-coded width silently
    truncates the view the moment a column is appended.
    """
    return [
        {
            "title": view.title,
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": row_count + 1,  # + the header
                "startColumnIndex": 0,
                "endColumnIndex": len(OUTPUT_HEADER),
            },
            "criteria": {str(_SOURCE_TAG_COLUMN): {"hiddenValues": list(view.hidden_tags)}},
        }
        for view in FILTER_VIEWS
    ]
