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
  geo_monitor.py       MHD/AH sitemap polling → new geo events
  discovery.py         per-geo .gov/.edu/authority search (SerpAPI)
  authority_filter.py  Ahrefs DR threshold filter for non-.gov/.edu
  page_detector.py     finds dept / resource page (not homepage)
  contact_extractor.py email + phone scraping, Hunter.io fallback
  link_checker.py      checks site for links to 16 competitor domains
  population.py        US Census API lookup for the geo
  output.py            Google Sheets writer + dedupe
tests/
docs/
  brief.md             original brief + feasibility (source of truth)
  architecture.md      system overview + diagram
  decisions.md         ADR log
  progress.md          running session log
```

All module files are currently stubs (docstring + responsibility, no implementation). Implementation begins Phase 1.

## Working rules (non-negotiable)

- Expert-engineer-grade code. No AI slop. No defensive `try/except` bloat. No comments that paraphrase the code.
- Comments only where logic is non-obvious. No section banners. No `# imports` headers.
- Type hints everywhere. Strict `pyright` must pass.
- Ask before guessing. If a decision could go two ways, surface both with trade-offs and stop.
- Liberty to research (SO, Reddit, Quora, GitHub issues, docs, Google). Cite non-obvious patterns in the relevant ADR or commit message.
- Playwright MCP is available — use it for real browser verification, do not trust raw HTML alone.
- Every non-trivial decision gets an entry in `docs/decisions.md`.
- End every working session by updating `docs/progress.md`.

## Reading order for any new session

1. `docs/brief.md` — source of truth.
2. This file (`CLAUDE.md`).
3. `docs/progress.md` — most recent session entry first.
4. `docs/decisions.md` if implementation choices are involved.
5. `docs/architecture.md` if touching cross-component behavior.

## Current state

Session 1 (2026-05-19): project scaffold + doc system only. No feature code.

- Repo layout, `pyproject.toml`, ruff + pyright config, `uv` env wired.
- Stub modules in place. Each has a one-line docstring describing responsibility.
- `config.py` and `logging.py` skeletons exist but load nothing real yet.
- `.env.example` lists every credential the project will need.
- One placeholder test asserts the package imports and reports its version.

## What's next (Phase 1 — Core MVP)

Order per feasibility doc Section 9:

1. Geo monitor — poll MHD + AH sitemaps, detect new city/county/state pages, emit events.
2. Discovery — SerpAPI queries per geo, filter to `.gov` / `.edu`.
3. Page detector — keyword-scored ranking of candidate URLs to surface the dept/resource page.
4. Contact extractor — `httpx` + parsing, Hunter.io fallback.
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

## Commands

```bash
uv sync                  # install/sync env from pyproject.toml + uv.lock
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ruff format --check .   # CI-style format check
uv run pyright           # strict type check
```
