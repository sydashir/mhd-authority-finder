"""Place keying for Source Tag (ADR-037)."""

from authority_finder.discovery.models import GeoRef
from authority_finder.geo_monitor.membership import key_for, place_key


class TestPlaceKey:
    def test_the_same_place_keys_the_same_at_different_levels(self) -> None:
        """MHD publishes Palos Verdes as a CITY under LA County; AH as a COUNTY.

        Both describe the same place. A level-sensitive key called this a miss and marked a
        both-sites place MHD-only — caught by hand-checking the two sitemaps, not by a test.
        """
        mhd = place_key(state="california", county="los-angeles", city="palos-verdes")
        ah = place_key(state="california", county="palos-verdes", city=None)
        assert mhd == ah == "california|palos-verdes"

    def test_a_state_page_keys_on_the_state_alone(self) -> None:
        assert place_key(state="minnesota", county=None, city=None) == "minnesota|"

    def test_different_places_do_not_collide(self) -> None:
        assert place_key(state="california", county=None, city="irvine") != place_key(
            state="california", county="ventura-county", city=None
        )

    def test_the_same_name_in_two_states_does_not_collide(self) -> None:
        assert place_key(state="california", county="orange-county", city=None) != place_key(
            state="new-york", county="orange-county", city=None
        )

    def test_key_for_reads_a_georef(self) -> None:
        geo = GeoRef(
            site_id="mhd",
            url="https://x/serving/california/los-angeles/palos-verdes/",
            level="city",
            state="california",
            county="los-angeles",
            city="palos-verdes",
        )
        assert key_for(geo) == "california|palos-verdes"
