"""The CISA registry as a wrong-state oracle for .gov (ADR-035).

ADR-033 kept discovery/registry.py unwired after measuring that registry-first DISCOVERY
loses the best prospects, and predicted its real value was wrong-state DERIVATION instead.
This is that use. The registry carries an authoritative State for all 16,406 US .gov domains,
so `candidate_state` no longer has to guess from the domain string.

Every fixture is a row that actually SHIPPED to the client and was deleted by hand in S48.
"""

import pytest

from authority_finder.page_detector.geography import candidate_state


class TestRegistryDerivesStatesTheStringRulesCannott:
    """These are the rows that reached the client filed under the wrong state."""

    @pytest.mark.parametrize(
        ("url", "state"),
        [
            # Shipped under MISSISSIPPI at HIGH trust, with a working intake email.
            ("https://lacounty.gov/", "california"),
            ("https://delcopa.gov/", "pennsylvania"),
            ("https://phila.gov/", "pennsylvania"),
            ("https://kingcounty.gov/", "washington"),
            ("https://sandiegocounty.gov/", "california"),
            ("https://dupagecounty.gov/", "illinois"),
            ("https://loraincountyohio.gov/", "ohio"),
            ("https://westfargond.gov/", "north-dakota"),
            ("https://nantucket-ma.gov/", "massachusetts"),
            ("https://elizabethtown-ny.gov/", "new-york"),
            ("https://newmarlboroughma.gov/", "massachusetts"),
            ("https://washcowisco.gov/", "wisconsin"),
            ("https://loudoun.gov/", "virginia"),
        ],
    )
    def test_wrong_state_rows_are_now_derivable(self, url: str, state: str) -> None:
        assert candidate_state(url) == state


class TestNoRegressionOnWhatAlreadyWorked:
    """The registry must not override or contradict the rules that were already right."""

    @pytest.mark.parametrize(
        ("url", "state"),
        [
            ("https://pinellas.gov/", "florida"),
            ("https://dconc.gov/", "north-carolina"),  # _KNOWN_GOV_STATES override
            ("https://mh.alabama.gov/", "alabama"),
            ("https://health.maryland.gov/", "maryland"),
            ("https://co.orange.ca.us/", "california"),  # .us suffix rule
        ],
    )
    def test_known_good_domains_keep_their_state(self, url: str, state: str) -> None:
        assert candidate_state(url) == state

    def test_edu_still_defers_to_the_scorecard(self) -> None:
        """.edu geography comes from the College Scorecard (ADR-024), not from here."""
        assert candidate_state("https://ucr.edu/") is None

    def test_a_federal_domain_asserts_no_state(self) -> None:
        """Federal bodies have no state; asserting one would hard-reject on a false premise."""
        for url in ("https://nrd.gov/", "https://cdc.gov/", "https://samhsa.gov/"):
            assert candidate_state(url) is None, url
