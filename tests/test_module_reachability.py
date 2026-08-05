"""Every module that claims to be part of the product must actually be REACHED by it.

This repo has shipped the same defect five times: something is built, tested, documented in
an ADR, and never connected to the code that runs.

  1. the `other` discovery bucket (ADR-006)   — counted, then discarded
  2. domain_rating in build_row                — accepted as a parameter, never assigned
  3. domain_rating in upsert_prospect          — absent from the INSERT column list
  4. found_on_url on CompetitorLink            — set on every link, read by nothing
  5. discovery/registry.py (ADR-029)           — module + tests + 16,406-row dataset, and
                                                 `discover.py` never imported it, so the
                                                 entire cost case was fiction

Numbers 2-4 are guarded by tests/output/test_field_paths.py, which checks that captured DATA
reaches the client. This file guards the other half: that a MODULE reaches the runtime.

Import-reachability is computed transitively from the real entry points, so a module counts
as reached only if the running program can actually get to it.
"""

import ast
import importlib.util
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "authority_finder"
BACKEND = ROOT / "backend"
PACKAGE = "authority_finder"

# What the product actually starts from.
ENTRY_POINTS: tuple[str, ...] = ("authority_finder.cli", "backend.app")

# Modules that are legitimately not imported by the runtime, each with a stated reason.
# Adding a name here is a deliberate claim that it is not meant to run in production.
NOT_RUNTIME: dict[str, str] = {}


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _all_modules() -> set[str]:
    """Product modules under src/authority_finder — the set that must be reachable."""
    return {
        _module_name(p, SRC.parent)
        for p in SRC.rglob("*.py")
        if "__pycache__" not in p.parts and _module_name(p, SRC.parent)
    }


def _backend_modules() -> set[str]:
    """Traversed but not policed here: backend is FastAPI-wired, not import-wired."""
    return {
        _module_name(p, ROOT)
        for p in BACKEND.rglob("*.py")
        if "__pycache__" not in p.parts and _module_name(p, ROOT)
    }


def _imports_of(module: str) -> Iterable[str]:
    """First-party modules imported by `module`, read from the source, not at runtime."""
    spec = importlib.util.find_spec(module)
    origin: str | None = spec.origin if spec is not None else None
    if origin is None or not origin.endswith(".py"):
        return ()
    tree = ast.parse(Path(origin).read_text())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names if a.name.startswith((PACKAGE, "backend")))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith((PACKAGE, "backend")):
                continue
            out.add(node.module)
            # `from x.y import z` where z is itself a module, not a name.
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


def _reachable() -> set[str]:
    seen: set[str] = set()
    stack = list(ENTRY_POINTS)
    known = _all_modules() | _backend_modules() | set(ENTRY_POINTS)
    while stack:
        current = stack.pop()
        if current in seen or current not in known:
            continue
        seen.add(current)
        # Importing a submodule imports its parent package too — otherwise every package
        # __init__ reads as an orphan.
        parts = current.split(".")
        stack.extend(".".join(parts[:i]) for i in range(1, len(parts)))
        stack.extend(_imports_of(current))
    return seen


def test_every_module_is_reachable_from_an_entry_point() -> None:
    orphans = sorted(_all_modules() - _reachable() - set(NOT_RUNTIME))
    assert not orphans, (
        "these modules are never imported by the running program:\n  "
        + "\n  ".join(orphans)
        + "\n\nEither wire it in, or add it to NOT_RUNTIME with a reason. A module with tests "
        "and an ADR that nothing imports is the defect this test exists to catch "
        "(discovery/registry.py shipped that way and made the whole cost case fiction)."
    )


def test_the_registry_is_wired_for_wrong_state_derivation() -> None:
    """It is finally reachable — as a geography oracle, not as a discovery source.

    ADR-033 measured registry-first DISCOVERY and reverted it (it lost cdph.ca.gov and gained
    octreasurer.gov), but predicted the table's real value was telling us which STATE a .gov
    belongs to. ADR-035 is that use: it is what stops lacounty.gov shipping under Mississippi.
    """
    assert "authority_finder.discovery.registry" in _reachable()
    assert "authority_finder.discovery.registry" in set(
        _imports_of("authority_finder.page_detector.geography")
    )


@pytest.mark.parametrize("name", sorted(NOT_RUNTIME))
def test_exempted_modules_still_exist(name: str) -> None:
    """An exemption for a deleted module hides the next orphan behind stale config."""
    assert name in _all_modules(), f"{name} is exempted but no longer exists"
