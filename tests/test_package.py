"""Smoke test: the package imports and exposes a version string."""

from __future__ import annotations

import authority_finder


def test_version_is_non_empty_string() -> None:
    assert isinstance(authority_finder.__version__, str)
    assert authority_finder.__version__
