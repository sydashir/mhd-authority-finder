# MHD Authority Site Finder

Automated backlink-prospecting tool. For every geo page on Mental Health Directory and Addiction Help, discovers `.gov` / `.edu` / high-authority sites in that geo, surfaces the relevant department or resource page, extracts contact info, checks for links to a fixed list of competitor domains, looks up population, and writes a row to a Google Sheet for outreach.

Source of truth for scope: [`docs/brief.md`](docs/brief.md).

## Setup

```bash
uv sync                       # create .venv and install pinned deps
cp .env.example .env          # fill in API keys
```

## Running

Nothing is wired to a CLI yet — Phase 1 (Session 2) adds a manual per-geo entry point. For now:

```bash
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format --check .  # format check
uv run pyright                # strict type check
```

## Docs

- [`CLAUDE.md`](CLAUDE.md) — persistent project memory + working rules.
- [`docs/brief.md`](docs/brief.md) — original brief + feasibility report (source of truth).
- [`docs/architecture.md`](docs/architecture.md) — components, data flow, external APIs.
- [`docs/decisions.md`](docs/decisions.md) — ADR log.
- [`docs/progress.md`](docs/progress.md) — running session log.
