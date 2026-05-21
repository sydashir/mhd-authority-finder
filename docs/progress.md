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

---

## 2026-05-21 — Session 2: Rules tightened, scope updates, integration targets confirmed

### Done

- Re-read `CLAUDE.md` and `docs/brief.md`.
- Confirmed first commit already had no AI attribution trailer (subject-only on remote `e87ef11`). Step 2 (amend + force-push) was a no-op — flagged rather than fabricated.
- Updated `~/.claude/settings.json` with `attribution.commit = ""` and `attribution.pr = ""`, merged into the existing `skipDangerousModePermissionPrompt: true`. Lives outside the repo so not committed.
- Appended three new working rules to `CLAUDE.md`:
  - No AI attribution on commits or PRs.
  - Conventional-commit style, subject ≤ 60 chars, lowercase imperative, no emojis.
  - Atomic commit-by-commit workflow.
- Added **ADR-002** (commit hygiene) and **ADR-003** (drop Hunter/Apollo from MVP scope) to `docs/decisions.md`.
- Removed Hunter / Apollo references from `docs/architecture.md` (component table, mermaid box, external-APIs table, scope-boundaries section). Contact extraction is now direct-scrape only for MVP.
- Created `docs/sites.md` with the confirmed integration targets (MHD = `inpatientmentalhealthfinder.com`, AH = `addictionhotline.com`), Rank Math sitemap structure, and URL patterns. Source: client's WordPress team, May 21 2026.
- Five atomic commits in the prescribed order:
  1. `docs: tighten commit + attribution rules` — `CLAUDE.md` only.
  2. `docs: drop hunter/apollo from mvp scope` — `decisions.md` (ADR-003) + `architecture.md`.
  3. `docs: log commit hygiene decision` — `decisions.md` (ADR-002).
  4. `docs: confirmed mhd + ah site details` — new `docs/sites.md`.
  5. `docs: progress log session 2` — this entry.

### Open decisions resolved this session

- **Hunter.io / Apollo:** dropped from MVP. Revisit only if first-batch contact coverage on real geos comes in below ~50%. (ADR-003.)
- **Run cadence:** manual-only for MVP. Matches feasibility doc Phase 1.
- **Ahrefs DR threshold:** 40, provisional. Will be tuned against real outreach response data once Phase 2 ships.
- **Integration targets:** confirmed — both client sites run WordPress + Rank Math with the same sitemap shape. Geo pages are regular Pages (not a CPT) and must be filtered out of `/page-sitemap*.xml` by URL pattern. `docs/sites.md` is now the canonical reference.

### Still open

- **Google Sheet target.** Sheet ID + service-account credentials. Not blocking until `output.py` is built.
- **SerpAPI vs Google Custom Search.** Not blocking until `discovery.py` is built. SerpAPI is the leading candidate (operationally simpler).

### Blocked

Nothing blocked.

### What's next — Session 3

First real component: `geo_monitor`. With sites.md in hand we now know exactly what to fetch and parse.

1. Async fetcher for `sitemap_index.xml` → enumerate child page sitemaps.
2. Parse each `page-sitemap{N}.xml`, filter to geo URLs by per-site pattern (`/serving/{state}/{county}/{city}/` for MHD, `/{state}/{county}/{city}/` for AH).
3. Classify each URL as state / county / city by path-segment depth.
4. Persist last-seen-set to disk; diff on next run; emit `NewGeoPage` events.
5. Tests against a snapshot of each sitemap_index (fixture, not live network).

Open question for the user before Session 3:
- Where do we persist the "last seen URLs" state? Local file under `data/` is simplest; a tiny SQLite db is overkill for MVP but worth flagging.
