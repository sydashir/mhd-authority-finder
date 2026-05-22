"""Unit tests for monitor state persistence: load-missing, roundtrip, atomic-write recovery."""

from datetime import UTC, datetime
from pathlib import Path

from authority_finder.geo_monitor.models import SiteState
from authority_finder.geo_monitor.state import load_state, save_state, state_path


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    state = load_state("mhd", state_dir=tmp_path)
    assert state.last_run is None
    assert state.known_urls == set()


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    original = SiteState(
        last_run=datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC),
        known_urls={"https://x.example/a/", "https://x.example/b/"},
    )
    save_state("mhd", original, state_dir=tmp_path)
    loaded = load_state("mhd", state_dir=tmp_path)
    assert loaded.last_run == original.last_run
    assert loaded.known_urls == original.known_urls


def test_orphan_tmp_file_does_not_corrupt_load(tmp_path: Path) -> None:
    good = SiteState(
        last_run=datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC),
        known_urls={"https://x.example/good/"},
    )
    save_state("mhd", good, state_dir=tmp_path)

    final = state_path("mhd", state_dir=tmp_path)
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.write_bytes(b"{ this is half-written garbage")

    loaded = load_state("mhd", state_dir=tmp_path)
    assert loaded.known_urls == {"https://x.example/good/"}
    assert tmp.exists()


def test_save_creates_state_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "state"
    save_state("ah", SiteState(known_urls={"https://x.example/"}), state_dir=target)
    assert (target / "ah.json").is_file()
