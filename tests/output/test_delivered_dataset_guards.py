"""Run every in-pipeline guard against the numbers and addresses that actually SHIPPED.

A hand-curated blocklist drifts silently. Mine held three numbers while ten were live in the
client's sheet, and my own first audit reported ZERO hotlines because I only tested the three
I already knew about. A list is only trustworthy if something replays the real corpus through
it, so this replays the delivered dataset (frozen snapshot, no DB or network needed).

Snapshot: scratch/audit/live_sheet.json, the exact 2,279-row sheet as sent for review.
"""

import json
from pathlib import Path

import pytest

from authority_finder.contact_extractor.extract import is_national_hotline, is_placeholder_email
from authority_finder.output.models import OutputRow
from authority_finder.output.shared_phones import blank_shared_phones

SNAPSHOT = Path(__file__).resolve().parents[2] / "scratch" / "audit" / "live_sheet.json"

# Every national line found live in the delivered sheet, by hand, with what it actually is.
# A rep dialling any of these reaches a crisis service, not the prospect.
SHIPPED_HOTLINES = {
    "+18002738255": "988 Suicide & Crisis Lifeline (legacy 1-800-273-TALK)",
    "+18006624357": "SAMHSA National Helpline",
    "+18007997233": "National Domestic Violence Hotline",
    "+18006564673": "RAINN National Sexual Assault Hotline (shipped at HIGH trust)",
    "+18009506264": "NAMI HelpLine",
    "+18664887386": "Trevor Project",
    "+18009855990": "SAMHSA Disaster Distress Helpline",
    "+18002221222": "Poison Control",
    "+18004874889": "SAMHSA TTY",
    "+18007873224": "National Domestic Violence Hotline TTY",
}

SHIPPED_PLACEHOLDERS = ("contact@mysite.com", "info@mysite.com", "info@new.com")


def _snapshot() -> tuple[list[str], list[list[str]]]:
    if not SNAPSHOT.is_file():
        pytest.skip(f"delivered-dataset snapshot not present at {SNAPSHOT}")
    data = json.loads(SNAPSHOT.read_text())
    return data["hdr"], data["rows"]


def _column(header: list[str], rows: list[list[str]], name: str) -> list[str]:
    index = header.index(name)
    return [row[index] if index < len(row) else "" for row in rows]


class TestEveryShippedHotlineIsBlocked:
    @pytest.mark.parametrize(("number", "who"), sorted(SHIPPED_HOTLINES.items()))
    def test_number_is_blocked(self, number: str, who: str) -> None:
        assert is_national_hotline(number), f"{number} is {who}"

    def test_no_hotline_survives_the_delivered_corpus(self) -> None:
        """The replay: every phone that shipped, through the guard."""
        header, rows = _snapshot()
        survivors = [
            (phone, SHIPPED_HOTLINES[phone])
            for phone in _column(header, rows, "Phone")
            if phone in SHIPPED_HOTLINES and not is_national_hotline(phone)
        ]
        assert not survivors, f"national lines still publishable as an org's own phone: {survivors}"


class TestNoRealNumberIsCaught:
    def test_the_guard_does_not_eat_ordinary_contacts(self) -> None:
        """Zero false positives, measured against the whole delivered corpus.

        Anything the guard rejects must be a known national line — if this ever fails, the
        blocklist has started deleting real organisations' phone numbers.
        """
        header, rows = _snapshot()
        wrongly_blocked = sorted(
            {
                phone
                for phone in _column(header, rows, "Phone")
                if phone and is_national_hotline(phone) and phone not in SHIPPED_HOTLINES
            }
        )
        assert not wrongly_blocked, f"real numbers caught by the hotline guard: {wrongly_blocked}"


class TestSharedLineDetectionOnRealData:
    def test_the_seven_state_referral_line_is_caught_without_a_list(self) -> None:
        """+18009898137 sat on 7 organisations across 7 states. No curated list had it."""
        header, rows = _snapshot()
        w, g, p = header.index("Website"), header.index("Geo Served"), header.index("Phone")

        def cell(row: list[str], i: int) -> str:
            return row[i] if i < len(row) else ""

        built = [
            OutputRow(
                website=cell(r, w),
                specific_page="https://x/",
                email="",
                phone=cell(r, p),
                contact_source="",
                contact_trust="low",
                organization_description="",
                geo_served=cell(r, g),
                population=None,
                competitor_links="—",
                source_tag="MHD",
                date_added="2026-08-05",
                confidence="low",
            )
            for r in rows
        ]
        cleaned, blanked = blank_shared_phones(built)
        assert blanked > 0
        assert all(row.phone != "+18009898137" for row in cleaned)


class TestEveryShippedPlaceholderIsBlocked:
    @pytest.mark.parametrize("email", SHIPPED_PLACEHOLDERS)
    def test_placeholder_is_rejected(self, email: str) -> None:
        assert is_placeholder_email(email)

    def test_no_placeholder_survives_and_no_real_address_is_caught(self) -> None:
        header, rows = _snapshot()
        emails = [e for e in _column(header, rows, "Email") if e]
        survivors = [
            e for e in emails if e.lower() in SHIPPED_PLACEHOLDERS and not is_placeholder_email(e)
        ]
        assert not survivors, survivors
        caught = sorted({e for e in emails if is_placeholder_email(e)})
        unexpected = [e for e in caught if e.lower() not in SHIPPED_PLACEHOLDERS]
        assert not unexpected, f"real addresses caught by the placeholder guard: {unexpected}"
