# Progress Log

Append-only running log, newest entry at the bottom. Every working session ends with an entry here: what got done, what's next, what's blocked, anything to surface to the user.

---

## 2026-05-19 — Session 1: Scaffolding + doc system

### Done

- Read `docs/brief.md` end-to-end (original brief from Jake + feasibility report).
- Installed `uv` 0.11.15 to `~/.local/bin/uv` (user-scoped; not previously on this machine).
- Created `CLAUDE.md` at repo root — persistent project memory for future sessions.
- Created `docs/architecture.md` — components, data flow, external APIs, mermaid diagram mirroring feasibility Section 4. Phase 2 components marked.
- Created `docs/decisions.md` with **ADR-001** documenting the locked stack (Python 3.12, `uv`, `ruff`, `pyright` strict, `pytest`, `httpx` async, `pydantic-settings`, `structlog`) with explicit alternatives and rationale.
- Scaffolded the project:
  - `pyproject.toml` (uv-managed, py312, deps pinned).
  - `src/authority_finder/` with `__init__.py` exposing `__version__`.
  - `config.py` — `pydantic-settings` skeleton typed against every env var in `.env.example`.
  - `logging.py` — `structlog` JSON setup, single `configure()` entry point.
  - Stub modules with docstrings only: `geo_monitor`, `discovery`, `authority_filter`, `page_detector`, `contact_extractor`, `link_checker`, `population`, `output`.
  - `tests/test_package.py` — imports the package, asserts `__version__` is a non-empty string.
  - `.gitignore`, `.env.example`, `README.md`.
  - `ruff` + `pyright` config inside `pyproject.toml`.
- Verified clean state: `uv sync`, `ruff check .`, `ruff format --check .`, `pyright`. All green.
- First commit: `chore: project scaffolding + doc system`.

### Decisions made this session (full rationale in `docs/decisions.md`)

- ADR-001 — full stack locked.

### Open questions for the user (need answers before Phase 1)

1. **MHD + AH sitemap URLs.** What are the canonical sitemap URLs we should poll? Are there separate sitemaps for city / county / state pages, or one unified sitemap that we filter by URL pattern?
2. **Google Sheet target.** Which sheet ID (or shall we create a new one)? Service account credentials available, or do we need to provision them?
3. **SerpAPI vs Google Custom Search.** Either works; SerpAPI is simpler operationally, Custom Search is cheaper at high volume. Preference?
4. **Ahrefs DR threshold (Phase 2).** Default DR 40+ — accept, or different?
5. **Hunter.io vs Apollo.** Either works as fallback for emails. Existing subscription with either?
6. **Run cadence.** Geo monitor polling interval — hourly, daily, on-demand only for MVP?

### Blocked

Nothing blocked.

### What's next

Phase 1 implementation begins next session. Order:

1. `geo_monitor` — sitemap polling, geo extraction, diff against persistent state.
2. `discovery` — SerpAPI queries per geo for `.gov` / `.edu`.
3. `page_detector` — keyword-scored ranking.
4. `contact_extractor` — direct scrape + Hunter.io fallback.
5. `population` — US Census API.
6. `output` — Google Sheets append + dedupe.
7. CLI wrapper for manual end-to-end runs per geo.

Phase 1 success criterion: feed a known MHD geo URL on the CLI, get at least one correct row appended to the Google Sheet with `.gov`/`.edu` site, dept page, contact info (or flagged), and population.
