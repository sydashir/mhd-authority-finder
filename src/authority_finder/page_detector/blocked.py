"""Classify why a candidate could not be fetched, so blocks can be surfaced not swallowed.

A candidate that fails to fetch currently disappears with no trace. Some of those failures
mean "this page does not exist" — fine to drop. Others mean "this organisation is real and
reachable by a human, but refuses automation": ncala.org, the brief's own named example,
returns HTTP 202 with a meta-refresh into a Sucuri CAPTCHA that Playwright cannot pass either.

Dropping those silently repeats ADR-006, where an uncounted bucket read zero for months and
nobody noticed the queries could not populate it. These are counted, named, and handed to the
client for manual outreach.
"""

from enum import Enum


class BlockReason(Enum):
    CAPTCHA = "captcha"
    FORBIDDEN = "forbidden"
    SSL = "ssl"
    ROBOTS = "robots"
    UNREACHABLE = "unreachable"


# A 202 on a public page is not "accepted, processing" — in the wild it is a bot-wall serving
# a challenge (Sucuri/GoDaddy sgcaptcha), which is exactly how ncala.org presents.
_CAPTCHA_MARKERS = ("202 from", "sgcaptcha", "captcha", "challenge", "429 from")
_FORBIDDEN_MARKERS = ("403", "forbidden", "access denied")
_SSL_MARKERS = ("ssl", "certificate", "cert_")
_ROBOTS_MARKERS = ("robots",)

_SURFACED = frozenset({BlockReason.CAPTCHA, BlockReason.FORBIDDEN, BlockReason.SSL})


def classify_block(error_message: str) -> BlockReason:
    """Why the fetch failed. Order matters: robots is checked before the HTTP markers so a
    robots refusal is never miscounted as the site blocking us."""
    text = error_message.lower()
    if any(m in text for m in _ROBOTS_MARKERS):
        return BlockReason.ROBOTS
    if any(m in text for m in _CAPTCHA_MARKERS):
        return BlockReason.CAPTCHA
    if any(m in text for m in _FORBIDDEN_MARKERS):
        return BlockReason.FORBIDDEN
    if any(m in text for m in _SSL_MARKERS):
        return BlockReason.SSL
    return BlockReason.UNREACHABLE


def is_blocked(reason: BlockReason) -> bool:
    """True when a human could still reach this org, so it belongs on the manual-visit list.

    ROBOTS is excluded because we chose not to fetch it; UNREACHABLE because there is nothing
    at the other end to visit.
    """
    return reason in _SURFACED
