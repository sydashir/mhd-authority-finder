"""Unparsed sitemap URLs must be COUNTED and NAMED (ADR-031).

This is the ADR-006 uncounted-drop pattern, in the monitor. An unrecognised URL returned None
and vanished, so "we have no county pages" and "we cannot parse the county pages" looked
identical from the outside. That hid 9 AH and 2,848 MHD geo pages until someone asked.

Non-geo pages (/contact/, /facilites/…) are legitimately unparsed and vastly outnumber the
interesting ones, so the signal has to be the SHAPE — repeated first path segments — rather
than a flat list nobody will read.
"""

from authority_finder.geo_monitor.monitor import summarise_unparsed


class TestSummary:
    def test_groups_by_first_path_segment(self) -> None:
        s = summarise_unparsed(
            [
                "https://x.com/support-groups/california/orange-county/",
                "https://x.com/support-groups/california/los-angeles/",
                "https://x.com/contact/",
            ]
        )
        assert s["support-groups"].count == 2

    def test_keeps_an_example_url_so_the_shape_is_visible(self) -> None:
        s = summarise_unparsed(["https://x.com/ocd-treatment/tn/davidson-county/nashville/"])
        assert "ocd-treatment" in s["ocd-treatment"].example

    def test_a_deep_repeated_shape_is_flagged_as_suspicious(self) -> None:
        """Many URLs sharing a prefix AND being multi-segment is what a missed geo type
        looks like — a one-off /contact/ page is not."""
        urls = [f"https://x.com/support-groups/california/city{n}/" for n in range(9)]
        s = summarise_unparsed(urls)
        assert s["support-groups"].suspicious is True

    def test_shallow_one_off_pages_are_not_flagged(self) -> None:
        s = summarise_unparsed(["https://x.com/contact/", "https://x.com/thank-you/"])
        assert all(not v.suspicious for v in s.values())

    def test_empty_input(self) -> None:
        assert summarise_unparsed([]) == {}
