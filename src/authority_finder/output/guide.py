"""The "How to read this" legend, generated from OUTPUT_HEADER (ADR-041).

The legend was previously written by a one-off script and then hand-maintained, so it drifted:
it documented 15 columns while the sheet had 19. A client reading it was told nothing about
the four newest columns — including the one whose relationship to Competitor Links caused the
confusion this module exists to resolve.

Generating it from :data:`OUTPUT_HEADER`, with a test that every column has an entry, makes
the drift impossible rather than merely unlikely.
"""

from authority_finder.output.models import OUTPUT_HEADER

GUIDE_TAB = "How to read this"
TITLE = "AuthorityScout — how to read this sheet"

# column -> (what it means, what a blank means). Keyed by the exact OUTPUT_HEADER string.
COLUMN_GUIDE: dict[str, tuple[str, str]] = {
    "Website": ("The organisation's domain — who you are pitching.", "never blank"),
    "Specific Page": (
        "The page to open. Where this organisation already links to a directory, this IS the "
        "page carrying those links.",
        "never blank",
    ),
    "Email": ("Best contact address found on the site.", "no address found on the page"),
    "Phone": (
        "Best phone found on the site.",
        "no phone found, or the number was a national crisis line and was removed",
    ),
    "Contact Source": (
        "Where the address came from: a same-domain mailto, a contact-page hop, or an "
        "off-domain link.",
        "no email found",
    ),
    "Contact Trust": (
        "How safe the EMAIL is to use. high = a department or role inbox on the "
        "organisation's own domain.",
        "never blank",
    ),
    "Organization Description": (
        "A snippet from the page, to jog your memory. Scraped text, not written copy.",
        "no snippet captured",
    ),
    "Geo Served": ("The directory page this prospect was found for.", "never blank"),
    "Population": (
        "US Census ACS5 2024 population of that geography.",
        "Census publishes no figure for that place (mostly neighbourhoods)",
    ),
    "Competitor Links": (
        "SUBSET FLAG over Addiction Directories: which of the 16 competitor domains named in "
        "the original brief this organisation links to. Use it to answer 'are they already "
        "linking to a competitor of ours?'. Everything here also appears in Addiction "
        "Directories.",
        "never blank — '—' means none of the named 16",
    ),
    "Source Tag": (
        "Which of your directories this prospect serves. 'Both' means the geography is "
        "published on both sites.",
        "never blank",
    ),
    "Date Added": ("When the row was produced.", "never blank"),
    "Confidence": (
        "How confident we are that Specific Page is the RIGHT page — separate from Contact "
        "Trust, which grades the email.",
        "never blank",
    ),
    "Domain Rating": (
        "Ahrefs Domain Rating (0-100).",
        "the site is .gov or .edu — deliberately not scored, since their authority is not in "
        "question",
    ),
    "Contact Found On": (
        "The page the email and phone came from, when that differs from Specific Page.",
        "one page did both jobs — the contact is on the Specific Page itself",
    ),
    "Addiction Directories": (
        "FULL LIST: every addiction/treatment directory this organisation links to — the 16 "
        "named in the brief AND every directory added since. This is the growing list; "
        "Competitor Links is the subset of it that matches the original 16.",
        "never blank — '—' means none found",
    ),
    "Mental Health Directories": (
        "FULL LIST: every therapist-finder or mental-health provider directory linked from "
        "the page.",
        "never blank — '—' means none found",
    ),
    "Support Groups": (
        "FULL LIST: every peer recovery fellowship or mutual-aid group linked from the page, "
        "national or local (AA, SMART Recovery, a county AA intergroup).",
        "never blank — '—' means none found",
    ),
    "Support Groups Found On": (
        "The page those support-group links actually appear on, when that differs from "
        "Specific Page.",
        "nothing to point at — the links are on Specific Page, or none were found",
    ),
}

_NOTES: list[tuple[str, str]] = [
    (
        "HOW THE LINK COLUMNS RELATE",
        "Addiction Directories / Mental Health Directories / Support Groups are three "
        "CATEGORIES, and each holds everything found in that category. Competitor Links is "
        "not a fourth category — it is a flag marking which entries in Addiction Directories "
        "are among the 16 domains named in the original brief. A domain in Competitor Links "
        "will ALWAYS also appear in Addiction Directories.",
    ),
    (
        "WHY THE LISTS GROW",
        "The tool keeps every outbound domain it sees. New directories and groups are "
        "proposed for review in the dashboard and only appear in these columns once a human "
        "approves them — nothing is added automatically.",
    ),
    (
        "ROW ORDER",
        "Sorted by Contact Trust first: all high-trust rows, then medium, then low. Within "
        "each band, organisations that already link to a competitor come first.",
    ),
    (
        "BEFORE A MAIL MERGE",
        "De-duplicate on the Email column. Some organisations legitimately serve many "
        "geographies, so one address can appear on several rows.",
    ),
]


def build_guide_rows() -> list[list[str]]:
    """The legend as a 3-column grid, in OUTPUT_HEADER order."""
    rows: list[list[str]] = [
        [TITLE, "", ""],
        ["", "", ""],
        ["Tab", "Prospects", "the deliverable. One row per (organisation, geography)."],
        ["", "", ""],
        ["COLUMN", "MEANING", "WHAT A BLANK MEANS"],
    ]
    for column in OUTPUT_HEADER:
        meaning, blank = COLUMN_GUIDE[column]
        rows.append([column, meaning, blank])
    for heading, body in _NOTES:
        rows.extend([["", "", ""], [heading, body, ""]])
    return rows
