"""The Both value must exist in the DB enum, not just in Python (ADR-037)."""

from authority_finder.db.models import SourceTag
from authority_finder.output.models import source_tag_for


def test_both_is_a_source_tag() -> None:
    assert SourceTag.Both.value == "Both"


def test_the_original_values_are_untouched() -> None:
    assert SourceTag.MHD.value == "MHD"
    assert SourceTag.AH.value == "AH"


def test_every_value_the_sheet_can_emit_is_in_the_enum() -> None:
    for sites in ({"mhd"}, {"ah"}, {"mhd", "ah"}):
        assert SourceTag(source_tag_for(sites))
