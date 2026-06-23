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
  domains.py           COMPETITOR_DOMAINS (16) + FEDERAL_DOMAINS shared lists
  robots.py            shared robots.txt checker + USER_AGENT
  fetching/            shared two-tier fetcher (httpx → Playwright on 403/SSL, ADR-007)
    models.py            PageContent / PageLink / fetch errors / BrowserFetcher protocol
    fetcher.py           PageFetcher + parse_html (politeness, caps, escalation)
    browser.py           PlaywrightBrowserFetcher (lazy, reused, lock-serialized)
  discovery/           per-geo .gov/.edu candidate search (SerpAPI, package)
    models.py            GeoRef / SearchResult / CandidateSite / DiscoveryResult
    serpapi_client.py    async google_light client + disk cache + billed counter
    queries.py           per-level query templates (pure)
    classify.py          tldextract classification + state-portal dedupe (ADR-005)
    discover.py          discover_for_geo / discover_many orchestrators
  authority_filter.py  Ahrefs DR threshold filter for non-.gov/.edu
  page_detector/       finds dept / resource page, not homepage (package, ADR-006)
    models.py            PageSignal / DetectedPage / CandidateOutcome / DetectionResult
    prefilter.py         pre-fetch rejection: competitor / federal / junk URLs (pure)
    fetcher.py           polite HTML fetch + parse (robots, caps, 2MB, text/html only)
    scorer.py            explainable signal scoring + confidence bands (pure)
    detector.py          per-candidate pipeline + bounded crawl fallback (≤6 fetches)
    orchestrator.py      detect_for_geo
  contact_extractor/   email + phone scraping (direct only, ADR-003/007, package)
    models.py            EmailHit / PhoneHit / ContactSet / ExtractionResult
    extract.py           pure email/phone extractors + guards + ranking
    contact_page.py      contact/staff-directory link discovery (pure)
    orchestrator.py      extract_for_geo + bounded contact-page fallback
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
- Session 4 (2026-06-13): `discovery` complete and live-validated — SerpAPI `google_light` page-1 client with disk cache + quota counters, per-level query templates, tldextract classification with state-portal dedupe exception (ADR-005), orchestrator, `discover` CLI command, 34 unit tests + 1 `live_paid` smoke test. Live run: 5 geos, 19 billed searches, 127 candidates.
- Session 5 (2026-06-13): `page_detector` complete and live-validated (ADR-006) — shared `domains.py` (competitor + federal exclusions) and `robots.py`, pre-filter, polite HTML fetcher, explainable scorer with wrong-state hard reject and topic-relevance confidence cap, bounded crawl fallback (≤6 fetches), `detect` CLI with `--in/--out` chaining. Live: 127 candidates → 54 detected (23 high / 21 med / 10 low); blind sample: high 8/8, medium 5/12. Known issue: 27% of candidates 403-block our honest UA.
- Session 6 (2026-06-17): shared two-tier `fetching/` (httpx → Playwright on 403/SSL) + `contact_extractor` complete and live-validated (ADR-007). Playwright recovered 14/35 of Session 5's fetch-failures; extraction email coverage 73% (.gov 70 / .edu 75), phone 81%. Hardened by a 5-lens adversarial audit (ID-number phones, template/DSN/version-pin emails, multi-dot obfuscation, ranking) + glued-digit guard. `extract` CLI chains from detection. `phonenumbers==9.0.32`; `playwright` promoted to runtime dep.
- Session 8 (2026-06-23): **contact attribution hardening (ADR-009).** Body-text emails domain-constrained to the candidate's registrable domain (`EmailHit.same_domain`); page-detection `Confidence` split from a new **Contact Trust** band + **Contact Source** provenance column; cross-domain mailto (e.g. the live `info@frsn.org` third-party case) flagged "mailto (off-domain)" / `low` rather than shown as trusted; ucdenver `admissions@` → `low`. Sheets `replace` mode added for value-correction full refresh. Live re-run: 0 billed, migration + idempotency clean, trust distribution high 1 / medium 27 / low 40. 228 tests.
- Session 7 (2026-06-19): **Phase 1 MVP COMPLETE + live Sheet verified.** `population/` (ACS5-2024 keyed Census lookup — keyless retired ~May 2026 → free key required, degrades to not_found without one) + `output/` (brief-exact row schema, CSV writer, idempotent Google Sheets writer) + `pipeline.py` + `run` CLI (full chain → CSV `--dry-run` or live Sheet). ADR-008. **Live close:** leaked `service-account.json` (committed S6) was purged from git history AND the key was rotated in GCP (gate verified `private_key_id` changed); live run over the 5 cached geos wrote **69 rows to the Google Sheet at 0 billed searches**, idempotent re-run appended 0, no fabrication. Population blank (no `CENSUS_API_KEY` yet). Known limitation: body-text contacts can be a third-party org referenced on the page (Phase 1.x: domain-constrain body-text emails/phones). `google-api-python-client==2.197.0`, `google-auth==2.55.0`.

## What does `run` do

`python -m authority_finder.cli run --site {mhd|ah|both} [--limit N] [--level …] [--dry-run] [--out FILE]` — the product. Chains monitor-state → discover (SerpAPI, cached) → detect → extract → populate (Census) → assemble brief-column rows → write CSV (`--dry-run`) or append to the Google Sheet (idempotent, dedupe by domain+geo). Per-geo isolation; prints a funnel summary.

## What's next (Phase 2 — Automation + Authority Sites)

Phase 1 is shipping rows. Remaining (feasibility doc Phase 2):
- `authority_filter` (component 3) — Ahrefs DR threshold for non-.gov/.edu authority orgs (ncala.org-type); needs unrestricted query variants since `site:`-filtered discovery can't surface them.
- `link_checker` (component 6) — crawl each site for outbound links to the 16 competitor domains (`COMPETITOR_DOMAINS` already in `domains.py`).
- Automated/scheduled triggers on new geo pages; re-validation runs.

Immediate operational follow-ups (not code): rotate the GCP service-account key; add a free `CENSUS_API_KEY` to light up population.

### Historical Phase-1 order (all shipped)

Per feasibility doc Section 9 — items 1 (geo monitor, S3), 2 (discovery, S4), 3 (page detector, S5), 4 (contact extractor, S6), 5 (population, S7), 6 (output, S7), 7 (`run` CLI, S7):
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

**ABSOLUTE RULE (user-stated, non-negotiable):** every commit and every push is done as **`sydashir`** and ONLY `sydashir` — never any other GitHub account, ever. Commit author is always `sydashir <meetashirr@gmail.com>`; never Claude, never a `Co-Authored-By`/"Generated with" trailer, never another identity. The active `gh` account on this machine often defaults to `dev778d`, so before any push verify and, if needed, push with the sydashir token (`gh auth token -u sydashir`) or `gh auth switch -u sydashir`. If pushing as sydashir is somehow impossible, STOP and tell the user — do not push as anyone else.

## Commands

```bash
uv sync                  # install/sync env from pyproject.toml + uv.lock
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ruff format --check .   # CI-style format check
uv run pyright           # strict type check
```
