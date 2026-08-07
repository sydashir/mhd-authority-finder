"""The two gates between a classifier's opinion and the client's sheet (ADR-040).

The learning layer exists to find what hand-written seed lists miss. It must not also become
a way for a machine's guess to reach a deliverable unreviewed — the delivered dataset is what
the client acts on, and a wrong "links to a support group" claim wastes a rep's outreach.

So there are two separate questions, and they are answered separately:

1. :func:`is_promotable` — is this worth ASKING a human about? A domain must be seen on at
   least two independent pages and carry a confident bucket. One page linking something is as
   likely to be an accident as a signal, and a hedged classification is not evidence.
2. :func:`effective_bucket` — may this reach the CLIENT? Only if a human approved it. An LLM
   answer never qualifies on its own, however confident. The tool proposes; a person disposes.

Rejection is sticky by construction: a rejected domain fails gate 1 forever, so a
re-classification cannot resurrect what a reviewer already turned down.
"""

from dataclasses import dataclass

from authority_finder.link_checker.classify import LinkClass

MIN_PAGES = 2
MIN_CONFIDENCE = 0.8

_REAL_BUCKETS = frozenset(
    {
        LinkClass.addiction_directory.value,
        LinkClass.mental_health_directory.value,
        LinkClass.support_group.value,
    }
)


@dataclass(frozen=True)
class DomainRecord:
    """The subset of a ``link_domains`` row the gates actually reason about."""

    domain: str
    status: str
    bucket: str | None
    confidence: float | None
    page_count: int
    provenance: str


def is_promotable(record: DomainRecord) -> bool:
    """Whether this domain should be put in front of a reviewer."""
    if record.status != "candidate":
        return False
    if record.bucket not in _REAL_BUCKETS:
        return False
    if record.confidence is None or record.confidence < MIN_CONFIDENCE:
        return False
    return record.page_count >= MIN_PAGES


def effective_bucket(record: DomainRecord) -> LinkClass | None:
    """The bucket this domain contributes to the deliverable, or ``None``.

    ``None`` for anything not human-approved. This is the single choke point that keeps a
    candidate out of the client's sheet, so it stays deliberately dull.
    """
    if record.status != "approved" or record.bucket not in _REAL_BUCKETS:
        return None
    return LinkClass(record.bucket)
