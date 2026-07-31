"""Guards the Compose $-escaping rule (see scripts/write_compose_secrets.py).

A scrypt hash contains ``$``. Compose expands those when reading an env file, so an
unescaped AUTH_USERS reaches the container truncated and container login fails while local
login works — a silent, deploy-only break.
"""

from scripts.write_compose_secrets import compose_escape, needs_escaping

REAL_SHAPE = "AUTH_USERS=admin:scrypt$16384$8$1$8YubueW7geH/AFymLCDOuQ==$OXYpkX6gWk2nh+eFkj7v"


class TestEscaping:
    def test_every_dollar_is_doubled(self) -> None:
        assert compose_escape("a$b$c") == "a$$b$$c"

    def test_the_real_hash_shape_round_trips(self) -> None:
        """Compose collapses $$ back to $, so unescaping must return the original."""
        escaped = compose_escape(REAL_SHAPE)
        assert escaped.replace("$$", "$") == REAL_SHAPE

    def test_the_segment_that_actually_vanished_survives(self) -> None:
        """$OXYpkX6gWk2nh was expanded to empty, cutting AUTH_USERS from 92 chars to 78."""
        escaped = compose_escape(REAL_SHAPE)
        assert "$$OXYpkX6gWk2nh" in escaped

    def test_a_value_with_no_dollar_is_untouched(self) -> None:
        assert compose_escape("LOG_LEVEL=INFO") == "LOG_LEVEL=INFO"


class TestSelection:
    def test_lines_containing_a_dollar_are_selected(self) -> None:
        assert needs_escaping(REAL_SHAPE)

    def test_plain_lines_are_skipped(self) -> None:
        assert not needs_escaping("LOG_LEVEL=INFO")

    def test_comments_are_skipped(self) -> None:
        assert not needs_escaping("# a $comment")

    def test_a_dollar_in_the_key_only_is_not_selected(self) -> None:
        """Only the value side can break Compose interpolation."""
        assert not needs_escaping("PLAIN=value")
