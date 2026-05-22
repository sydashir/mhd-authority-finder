"""Persistent monitor state, one file per site.

State is stored as JSON at ``data/state/{site_id}.json`` with the shape::

    {"last_run": "2026-05-21T18:30:00+00:00", "known_urls": [...]}

Writes are atomic: we serialize into ``{path}.tmp`` and :func:`os.replace`
it onto the final filename so a process kill mid-write can never leave a
half-written ``site_id.json`` behind. A leftover ``.tmp`` is ignored by
:func:`load_state`; the previously-good file remains canonical.
"""

import os
from pathlib import Path

from authority_finder.geo_monitor.models import SiteState

DEFAULT_STATE_DIR = Path("data/state")


def state_path(site_id: str, *, state_dir: Path = DEFAULT_STATE_DIR) -> Path:
    """Return the on-disk path for a site's state file."""
    return state_dir / f"{site_id}.json"


def load_state(site_id: str, *, state_dir: Path = DEFAULT_STATE_DIR) -> SiteState:
    """Return the persisted state for ``site_id`` or an empty :class:`SiteState`."""
    path = state_path(site_id, state_dir=state_dir)
    if not path.is_file():
        return SiteState()
    return SiteState.model_validate_json(path.read_bytes())


def save_state(site_id: str, state: SiteState, *, state_dir: Path = DEFAULT_STATE_DIR) -> None:
    """Atomically persist ``state`` to ``data/state/{site_id}.json``."""
    state_dir.mkdir(parents=True, exist_ok=True)
    final = state_path(site_id, state_dir=state_dir)
    tmp = final.with_suffix(final.suffix + ".tmp")
    payload = state.model_dump_json(indent=2).encode("utf-8")
    with tmp.open("wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(final)
