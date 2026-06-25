# MHD Authority Site Finder

Automated backlink-prospecting tool. For every geo page on Mental Health Directory and Addiction Help, discovers `.gov` / `.edu` / high-authority sites in that geo, surfaces the relevant department or resource page, extracts contact info, checks for links to a fixed list of competitor domains, looks up population, and writes a row to a Google Sheet for outreach.

Source of truth for scope: [`docs/brief.md`](docs/brief.md).

## Setup

```bash
uv sync                       # create .venv and install pinned deps
cp .env.example .env          # fill in API keys
uv run playwright install chromium   # one-time, needed for `pytest -m live`
```

## Running

Copy `.env.example` → `.env` and fill in `SERPAPI_API_KEY`, `GOOGLE_SHEET_ID`, and (optionally)
`CENSUS_API_KEY`; put the Google service-account JSON at `service-account.json` (shared as Editor
on the sheet). Then:

```bash
uv run python -m authority_finder.cli run --site both            # full pipeline → live Sheet
uv run python -m authority_finder.cli run --site both --dry-run  # → local CSV instead
uv run python -m authority_finder.cli monitor                    # just diff the sitemaps
```

### Scheduler (auto-trigger on new geo pages)

The scheduler polls both sitemaps on an interval and runs the full pipeline **only for newly
published geo pages** (cost-safe — zero SerpAPI spend on quiet days), appending to the live Sheet
idempotently. Caps (`MAX_NEW_GEOS_PER_RUN`, `MAX_BILLED_SEARCHES_PER_RUN`) guard against a runaway
run. Interval is `RUN_INTERVAL_HOURS` (default daily). Runs identically on a laptop or in a container.

**On the host (Mac/Linux):**

```bash
uv run python -m authority_finder.cli schedule            # run forever: one tick now, then every N hours
uv run python -m authority_finder.cli schedule --once     # a single tick, then exit (cron / smoke test)
```

**In Docker** (same code, no changes to move hosts):

```bash
docker compose build
docker compose up -d          # scheduler runs detached, restarts on failure
docker compose logs -f        # structured JSON logs per tick
docker compose run --rm scheduler uv run python -m authority_finder.cli schedule --once   # one-shot
```

`docker-compose.yml` mounts `.env` and `service-account.json` **read-only** at runtime — secrets are
never baked into the image — and bind-mounts `./data` so the SerpAPI cache and monitor state survive
restarts (so a restart never re-processes already-seen geos).

### Dev

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
