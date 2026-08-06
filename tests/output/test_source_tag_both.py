"""Source Tag must be able to say "Both" (ADR-037).

The enum held MHD and AH only, so a prospect from a geography BOTH directories publish was
tagged with whichever run last touched it — in practice MHD. The client filtered
Source Tag = AH, got 22 rows out of 2,237, and concluded the AH half was never built. The
truth is the opposite: 2,099 of 2,237 rows serve both sites.

Ground truth is the sitemaps, not a guess: a place published by both directories yields
prospects that serve both.
"""

import pytest

from authority_finder.output.models import OUTPUT_HEADER, source_tag_for


class TestSourceTagFor:
    def test_both_sites_gives_both(self) -> None:
        assert source_tag_for({"mhd", "ah"}) == "Both"

    def test_one_site_names_that_site(self) -> None:
        assert source_tag_for({"mhd"}) == "MHD"
        assert source_tag_for({"ah"}) == "AH"

    def test_order_does_not_matter(self) -> None:
        assert source_tag_for({"ah", "mhd"}) == source_tag_for({"mhd", "ah"})

    def test_an_unknown_site_is_not_silently_dropped(self) -> None:
        """A new directory must fail loudly, not be mislabelled as one of the existing two."""
        with pytest.raises(ValueError, match="unknown site"):
            source_tag_for({"zzz"})

    def test_no_sites_is_refused(self) -> None:
        """Undeterminable attribution must never quietly default to MHD."""
        with pytest.raises(ValueError, match="no site"):
            source_tag_for(set())


class TestSchemaUnchanged:
    def test_source_tag_keeps_its_column_position(self) -> None:
        assert OUTPUT_HEADER.index("Source Tag") == 10
