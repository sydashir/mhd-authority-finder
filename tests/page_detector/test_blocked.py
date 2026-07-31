"""Blocked candidates must be COUNTED and NAMED, not silently dropped (ADR-006).

ncala.org — the brief's own named example — vanished from output with no trace. It is a
legitimate prospect sitting behind a Sucuri CAPTCHA; a human could contact it. Silently
losing it repeats the mistake that left ADR-006's `other` bucket reading zero for months.
"""

from authority_finder.page_detector.blocked import BlockReason, classify_block, is_blocked


class TestRealSignatures:
    def test_the_ncala_captcha(self) -> None:
        """Verified live: httpx 202 with a meta-refresh to /.well-known/sgcaptcha/."""
        assert classify_block("202 from https://ncala.org/") is BlockReason.CAPTCHA

    def test_hard_403_after_playwright(self) -> None:
        """Playwright already escalated and still got 403 — the site refuses automation."""
        assert (
            classify_block("403 after playwright escalation: https://x.org/")
            is BlockReason.FORBIDDEN
        )

    def test_plain_403(self) -> None:
        assert classify_block("403 from https://x.org/") is BlockReason.FORBIDDEN

    def test_ssl_failure(self) -> None:
        assert classify_block("SSLError: certificate verify failed") is BlockReason.SSL

    def test_robots_disallowed(self) -> None:
        """Not a block to report to the client — we chose not to fetch it."""
        assert classify_block("robots.txt disallows https://x.org/") is BlockReason.ROBOTS


class TestNotBlocks:
    def test_a_404_is_not_a_block(self) -> None:
        """The page is simply gone; nothing for a human to visit."""
        assert classify_block("404 from https://x.org/") is BlockReason.UNREACHABLE

    def test_a_timeout_is_not_a_block(self) -> None:
        assert classify_block("ConnectTimeout") is BlockReason.UNREACHABLE

    def test_empty_message(self) -> None:
        assert classify_block("") is BlockReason.UNREACHABLE


class TestWorthSurfacing:
    def test_captcha_and_forbidden_are_worth_a_human_visit(self) -> None:
        assert is_blocked(BlockReason.CAPTCHA)
        assert is_blocked(BlockReason.FORBIDDEN)

    def test_ssl_is_worth_a_human_visit(self) -> None:
        """A cert problem does not mean the org is not a prospect."""
        assert is_blocked(BlockReason.SSL)

    def test_robots_and_unreachable_are_not_surfaced(self) -> None:
        """robots is our own choice; unreachable means there is nothing to visit."""
        assert not is_blocked(BlockReason.ROBOTS)
        assert not is_blocked(BlockReason.UNREACHABLE)
