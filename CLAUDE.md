# MHD Authority Site Finder

Automated backlink-prospecting tool. For every geo page on Mental Health Directory (MHD) and Addiction Help (AH), discover `.gov` / `.edu` / high-DR authority sites in that geo, find the relevant department or resource page, pull contact info, check for links to a fixed list of competitor domains, look up population, and append the row to a Google Sheet for outreach.

This file is the durable handoff between sessions. Keep it accurate. If you change a rule, update it here.

## Stack (locked)

- Python **3.12**
- `uv` for env + dependency management
- `ruff` for lint and format (line length 100, target py312)
- `pyright` in **strict** mode
- `pytest` + `pytest-asyncio`
- `src/` layout
- Async-first I/O: `httpx`, `asyncio`
- Config via `pydantic-settings` reading `.env`
- Structured JSON logs via `structlog`

Pinned versions live in `pyproject.toml`. Bump deliberately, not opportunistically.

## Module layout

```
src/authority_finder/
  __init__.py          version + public surface
  config.py            pydantic-settings, loads .env
  logging.py           structlog setup
  cli.py               click CLI — `python -m authority_finder.cli`
  geo_monitor/         MHD/AH sitemap polling → new geo events (package)
    models.py            SiteConfig / GeoPage / SitemapEntry / MonitorRun / SiteState
    sites.py             MHD + AH SiteConfig instances
    states.py            US_STATE_SLUGS whitelist (ADR-004)
    sitemap_fetcher.py   async fetch: index → page sitemaps → regex filter
    url_parser.py        pure URL → GeoPage parser
    state.py             data/state/{site}.json persistence
    monitor.py           run_monitor orchestrator
  discovery.py         per-geo .gov/.edu/authority search (SerpAPI)
  authority_filter.py  Ahrefs DR threshold filter for non-.gov/.edu
  page_detector.py     finds dept / resource page (not homepage)
  contact_extractor.py email + phone scraping (direct only, MVP)
  link_checker.py      checks site for links to 16 competitor domains
  population.py        US Census API lookup for the geo
  output.py            Google Sheets writer + dedupe
tests/
docs/
  brief.md             original brief + feasibility (source of truth)
  sites.md             confirmed MHD/AH integration details (sitemaps, URL patterns)
  architecture.md      system overview + diagram
  decisions.md         ADR log
  progress.md          running session log
journal/               session journals (gitignored — see working rules)
```

`geo_monitor` is implemented; the remaining pipeline modules are stubs (docstring + responsibility, no implementation).

## Working rules (non-negotiable)

- Expert-engineer-grade code. No AI slop. No defensive `try/except` bloat. No comments that paraphrase the code.
- Comments only where logic is non-obvious. No section banners. No `# imports` headers.
- Type hints everywhere. Strict `pyright` must pass.
- Ask before guessing. If a decision could go two ways, surface both with trade-offs and stop.
- Liberty to research (SO, Reddit, Quora, GitHub issues, docs, Google). Cite non-obvious patterns in the relevant ADR or commit message.
- Playwright MCP is available — use it for real browser verification, do not trust raw HTML alone.
- Every non-trivial decision gets an entry in `docs/decisions.md`.
- End every working session by updating `docs/progress.md`.
- No AI attribution on commits or PRs. Never add `Co-Authored-By: Claude`, "Generated with Claude Code", or any similar trailer/footer. Commits are authored by the human only.
- Commit messages: short, conventional-commit style. Subject line ≤ 60 chars, lowercase, imperative ("add x" not "added x"). Body only when truly needed. No marketing language, no emojis.
- Commit-by-commit workflow: one logical change per commit. If you touch two unrelated things, that's two commits. Easier to review, easier to revert. Never batch unrelated work.
- Session journal (MANDATORY, self-triggered — the user will never remind you):
  - Journals live in `journal/` at repo root. `journal/` is gitignored.
  - File name: `journal/SESSION-{YYYY-MM-DD}-{short-slug}.md`
  - WHEN to write: (1) immediately when context usage becomes high (~90%+) or you anticipate compaction — write BEFORE compacting, never after; (2) at every natural session end; (3) before any risky long-running operation that could crash the session.
  - WHAT to write (detailed, not bullets-of-bullets): session goal; what was done with commit hashes; key decisions + reasoning; exact current state (what works, what's half-done, what's broken); live-run numbers if any; open questions; precise next steps so a fresh session can resume with zero re-discovery; any gotchas learned this session.
  - At the START of every session: check `journal/` for the most recent file and read it as part of context rebuild.
  - Update `journal/INDEX.md` (one line per session: date, slug, one-sentence summary) every time you write a journal.

## Reading order for any new session

1. `docs/brief.md` — source of truth.
2. This file (`CLAUDE.md`).
3. `docs/progress.md` — most recent session entry first.
4. `docs/decisions.md` if implementation choices are involved.
5. `docs/architecture.md` if touching cross-component behavior.

## Current state

As of Session 4-prep (2026-06-12):

- Sessions 1–2 (2026-05-19/21): scaffold, doc system, commit-hygiene rules (ADR-002), Hunter/Apollo dropped from MVP (ADR-003), integration targets confirmed in `docs/sites.md`.
- Session 3 (2026-05-22): `geo_monitor` complete and live-verified — async sitemap fetcher (tenacity retry, robots.txt, per-host semaphore), pure URL parser with state-slug whitelist (ADR-004), atomic state persistence under `data/state/`, orchestrator, `monitor` CLI command. 42 unit + 5 live tests.
- Session 4-prep (2026-06-12): session-journal rule + SessionStart hook installed (`.claude/`), full toolchain audit green, live baseline MHD 23 / AH 49 geo pages (0 new since Session 3), SerpAPI/httpx/tenacity research done for the discovery build.
- `discovery`, `page_detector`, `contact_extractor`, `population`, `output` (Phase 1) and `authority_filter`, `link_checker` (Phase 2) are still stubs.

## What's next (Phase 1 — Core MVP)

Order per feasibility doc Section 9 — item 1 (geo monitor) shipped in Session 3:

2. Discovery — SerpAPI queries per geo, filter to `.gov` / `.edu`. (Session 4)
3. Page detector — keyword-scored ranking of candidate URLs to surface the dept/resource page.
4. Contact extractor — `httpx` + HTML parsing, direct scrape only (ADR-003).
5. Population — US Census API.
6. Output — Google Sheets append + dedupe.
7. Manual trigger CLI to run end-to-end per geo.

Phase 2 (Ahrefs authority filter, competitor link checker, scheduled triggers) comes after Phase 1 is shipping rows.

## Conventions

- All I/O is async unless there is a specific reason not to. No blocking `requests`.
- Settings are typed (`pydantic-settings`). No `os.getenv` calls scattered through modules.
- Logs are JSON via `structlog`. No `print`, no stdlib `logging` calls in app code.
- Tests live under `tests/`, mirror the `src/authority_finder/` layout when meaningful.
- Commits: conventional style (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).

## Repo access

Remote `origin` is the private repo `sydashir/mhd-authority-finder`. Pushes require the `sydashir` GitHub account — if `gh auth status` shows a different active account, run `gh auth switch -u sydashir` before pushing.

## Commands

```bash
uv sync                  # install/sync env from pyproject.toml + uv.lock
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ruff format --check .   # CI-style format check
uv run pyright           # strict type check
```
