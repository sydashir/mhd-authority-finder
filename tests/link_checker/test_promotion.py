"""What is eligible to be PROPOSED to a human, and what may reach the client (ADR-040).

Two separate gates, deliberately:

* ``is_promotable`` decides what a reviewer is asked about. Too loose and the queue is noise
  nobody works through; too tight and the learning layer finds nothing.
* ``effective_bucket`` decides what reaches the client's sheet. Only seeds and human-approved
  domains pass. An LLM answer alone never does, however confident — the tool proposes, a
  person disposes.
"""

import pytest

from authority_finder.link_checker.classify import LinkClass
from authority_finder.link_checker.promotion import (
    MIN_CONFIDENCE,
    MIN_PAGES,
    DomainRecord,
    effective_bucket,
    is_promotable,
)


def _record(**kwargs: object) -> DomainRecord:
    base: dict[str, object] = {
        "domain": "example.org",
        "status": "candidate",
        "bucket": "support_group",
        "confidence": 0.9,
        "page_count": 3,
        "provenance": "llm",
    }
    return DomainRecord(**(base | kwargs))  # pyright: ignore[reportArgumentType]


class TestPromotionBar:
    def test_a_confident_domain_on_several_pages_is_proposed(self) -> None:
        assert is_promotable(_record())

    def test_one_page_is_not_enough(self) -> None:
        """A single page linking something is as likely an accident as a signal."""
        assert not is_promotable(_record(page_count=1))
        assert MIN_PAGES >= 2

    def test_a_hedged_classification_is_not_proposed(self) -> None:
        assert not is_promotable(_record(confidence=MIN_CONFIDENCE - 0.01))
        assert is_promotable(_record(confidence=MIN_CONFIDENCE))

    def test_an_unbucketed_domain_is_never_proposed(self) -> None:
        """'unknown' is a valid answer and must not become queue noise."""
        assert not is_promotable(_record(bucket=None))
        assert not is_promotable(_record(bucket="unknown"))

    def test_a_missing_confidence_is_not_treated_as_confident(self) -> None:
        assert not is_promotable(_record(confidence=None))


class TestRejectionIsSticky:
    def test_a_rejected_domain_is_never_re_proposed(self) -> None:
        """Otherwise every re-classification resurrects it and the queue never empties."""
        assert not is_promotable(_record(status="rejected", confidence=1.0, page_count=99))

    def test_an_already_approved_domain_is_not_re_proposed(self) -> None:
        assert not is_promotable(_record(status="approved"))


class TestOnlyApprovedReachesTheClient:
    def test_a_candidate_is_invisible_to_the_sheet(self) -> None:
        assert effective_bucket(_record(status="candidate")) is None

    def test_even_a_perfectly_confident_candidate_is_invisible(self) -> None:
        """Auto-add NOTHING. Confidence is not consent."""
        assert effective_bucket(_record(status="candidate", confidence=1.0)) is None

    def test_an_approved_domain_reaches_the_sheet(self) -> None:
        assert effective_bucket(_record(status="approved")) is LinkClass.support_group

    def test_a_rejected_domain_never_reaches_the_sheet(self) -> None:
        assert effective_bucket(_record(status="rejected")) is None

    def test_an_approved_domain_with_a_bad_bucket_is_ignored_not_crashed(self) -> None:
        assert effective_bucket(_record(status="approved", bucket="nonsense")) is None

    @pytest.mark.parametrize(
        "bucket",
        ["support_group", "addiction_directory", "mental_health_directory"],
    )
    def test_every_real_bucket_round_trips(self, bucket: str) -> None:
        assert effective_bucket(_record(status="approved", bucket=bucket)) is LinkClass(bucket)
