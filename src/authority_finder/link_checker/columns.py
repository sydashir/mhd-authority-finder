"""Assemble the deliverable's link columns from one page's findings (ADR-041).

The client read "Competitor Links: samhsa.gov" beside "Addiction Directories: drugrehab.com"
and reasonably concluded these were two unrelated lists. They are one list and a flag over it:

* A **category column** carries EVERY domain found in that category — the brief's original 16,
  the directories verified since, and anything a human later approves from the review queue.
  This is the "full list of domains to look for" the client asked for, and it grows.
* **Competitor Links** stays exactly the named 16 so the brief's question — does this
  organisation already link to one of OUR competitors? — remains answerable. It is a subset
  flag, not a separate universe.

The superset used to hold only by luck: ``COMPETITOR_DOMAINS`` is a subset of
``ADDICTION_DIRECTORIES``, so a live crawl always produced consistent columns. Rebuilding the
categories from stored domains broke it — 5 rows whose re-crawl failed kept their competitor
evidence while the category column went blank, telling the client an organisation links to no
directory directly beside a column naming one. Unioning the flag INTO its category here makes
the relationship structural, so the two can never disagree again regardless of what the
caller managed to fetch.
"""

from collections.abc import Mapping, Sequence

from authority_finder.link_checker.classify import LinkClass

# What a category cell says when the check ran and found nothing.
NONE_FOUND = "—"

# Which category each of the brief's competitor domains belongs to. They are all addiction
# directories; this names the relationship rather than leaving it implicit.
COMPETITOR_CATEGORY = LinkClass.addiction_directory


def _cell(domains: Sequence[str]) -> str:
    return "; ".join(sorted(set(domains))) or NONE_FOUND


def build_link_columns(
    *,
    competitor_domains: Sequence[str],
    bucketed: Mapping[LinkClass, Sequence[str]],
    support_group_pages: Sequence[str],
    all_domains: Sequence[str],
) -> dict[str, str]:
    """The link-related cells for one prospect row.

    ``bucketed`` maps a class to the domains classified into it. ``competitor_domains`` is
    merged into its category so the flag is always visible in the fuller list.
    """
    categories = {
        LinkClass.addiction_directory: [
            *bucketed.get(LinkClass.addiction_directory, ()),
            *competitor_domains,
        ],
        LinkClass.mental_health_directory: bucketed.get(LinkClass.mental_health_directory, ()),
        LinkClass.support_group: bucketed.get(LinkClass.support_group, ()),
    }
    return {
        "competitor_links": _cell(competitor_domains),
        "addiction_directories": _cell(categories[LinkClass.addiction_directory]),
        "mental_health_directories": _cell(categories[LinkClass.mental_health_directory]),
        "support_groups": _cell(categories[LinkClass.support_group]),
        # Provenance, not a finding — blank when there is nothing to point at.
        "support_groups_found_on": "; ".join(sorted(set(support_group_pages))),
        "outbound_domains": "; ".join(sorted(set(all_domains))),
    }
