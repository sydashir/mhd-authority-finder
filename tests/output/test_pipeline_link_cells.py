"""The pipeline must assemble link cells through the SHARED builder (ADR-041).

`build_link_columns` is unit-tested in tests/link_checker/test_columns.py. What that cannot
see is whether the pipeline actually calls it — and the reason this matters is a measured
defect: the pipeline and the re-classification path each built these cells their own way, so
5 rows ended up with a competitor domain in the flag column and nothing in its category.

These tests pin the join, not the arithmetic.
"""

import inspect

from authority_finder import pipeline
from authority_finder.link_checker.columns import build_link_columns
from authority_finder.output.models import OutputRow


class TestThePipelineUsesTheSharedBuilder:
    def test_it_imports_and_calls_build_link_columns(self) -> None:
        source = inspect.getsource(pipeline)
        assert "build_link_columns" in source, "the pipeline must not hand-roll these cells"

    def test_it_does_not_hand_assemble_the_competitor_cell(self) -> None:
        """The old line was `"; ".join(link_result.competitor_domains) or "—"`.

        Keeping it would let the flag be written without its category ever being unioned.
        """
        source = inspect.getsource(pipeline.run_pipeline)
        assert "join(link_result.competitor_domains)" not in source

    def test_the_builder_feeds_every_link_field_on_the_row(self) -> None:
        """Every key the builder emits must be a real OutputRow field, or it is dropped."""
        produced = build_link_columns(
            competitor_domains=[], bucketed={}, support_group_pages=[], all_domains=[]
        )
        for key in produced:
            assert key in OutputRow.model_fields, f"{key!r} is not an OutputRow field"

    def test_the_row_carries_a_cell_for_each_link_field(self) -> None:
        """Guards the reverse: a builder key silently missing from the deliverable."""
        produced = build_link_columns(
            competitor_domains=["samhsa.gov"],
            bucketed={},
            support_group_pages=[],
            all_domains=["samhsa.gov"],
        )
        row = OutputRow(
            website="x.edu",
            specific_page="https://x.edu/",
            email="",
            phone="",
            contact_source="",
            contact_trust="low",
            organization_description="",
            geo_served="California",
            population=None,
            source_tag="MHD",
            date_added="2026-08-07",
            confidence="low",
            **produced,
        )
        assert row.competitor_links == "samhsa.gov"
        # The whole point of ADR-041: the flag is visible in its category too.
        assert row.addiction_directories == "samhsa.gov"
