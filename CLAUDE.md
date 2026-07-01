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
  link_checker/        competitor backlink detection (component 6, ADR-011)
    models.py            CompetitorLink / LinkCheckResult
    check.py             find_competitor_links (registrable-domain match, pure)
    resources.py         resources/links-page picker (pure)
    orchestrator.py      check_links_for_candidate (detected page + 1 resources hop, ≤2 fetches)
  population.py        US Census API lookup for the geo
  output.py            Google Sheets writer + dedupe
  pipeline.py          full discover→detect→extract→links→populate→row chain
  scheduler/           scheduled auto-triggers (component 8, ADR-012)
    models.py            IncrementalRunResult / RunOutcome
    incremental.py       run_incremental — new-geos-only, cost-safe, state-on-success
    runner.py            APScheduler tick loop + per-site wiring (run_tick / scheduled_tick)
  db/                  Postgres source-of-truth (Phase A, ADR-013)
    models.py            SQLAlchemy 2.x async models (prospects/runs/geos; native enums)
    session.py           make_engine / make_session_factory
    repository.py        async reads/writes (filters, pagination, count, runs listing)
    ingest.py            OutputRow→DB bridge (persist_prospects / persist_pipeline_run)
  cli.py               + schedule command (--once / --interval-hours) + run --persist-db
Dockerfile             scheduler image (py3.12 + uv + chromium)
docker-compose.yml     secrets read-only + data/ volume; runs scheduler + postgres:16 (host 5433)
alembic/               migrations (sync env.py, psycopg 3); alembic.ini at repo root
backend/               FastAPI API over Postgres (Phase B, ADR-014)
  app.py                 app factory + lifespan (engine/sessionmaker on app.state) + CORS + sweep
  deps.py                get_session / get_sessionmaker request dependencies
  schemas.py             pydantic v2 response models (ProspectOut / RunOut / PageOf[T])
  jobs.py                background run execution (cost-safe incremental/full) + orphan-sweep
  routers/               health / stats / prospects / runs / export (POST /runs trigger, POST /export/sheet)
frontend/              AuthorityScout — React dashboard over the API (Phase C, ADR-015/016) — Vite + TS + Tailwind v4 + TanStack Query
  src/api/               typed client + hooks (Prospect/PageOf/Run/Stats; getRuns/triggerRun, useRuns polling, useTriggerRun, exportSheet)
  src/lib/               theme (dark-first token toggle), format (timeAgo/duration), csv builder
  src/components/         Sidebar (nav), Topbar, Logo, ProspectsScreen, RunsScreen, RunNowButton, StatCards, ProspectsTable (sort+columns), FilterBar, Pagination, ProspectDrawer (actionable), ExportActions, Toast, badges (incl. RunStatusBadge), states
  src/index.css          Tailwind v4 + CSS-variable design tokens (dark+light) + badge classes
  src/App.tsx            shell + view switch (ProspectsScreen | RunsScreen) + shared toast
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
- Session 17 (2026-07-01): **SaaS Phase C2 — Runs screen + "Run now" + live status (ADR-017). UI COMPLETE.** The last UI screen, into the shell slot C1-redesign reserved. Backend (GET/POST /runs from Phase B) untouched; UI talks only to the API. **View switching** (no router): Sidebar nav clickable, App renders `ProspectsScreen` (extracted from App) or `RunsScreen`. **Runs list:** `GET /runs` as a dense themed table (Site, RunStatusBadge running/success/failed, `timeAgo` timestamps, duration, geos/rows/billed, error notes; billed>0 tinted amber) + loading/empty/error states. **Run now:** popover picks site (MHD/AH/Both) + mode — **cost-safe "New geos only" default** ("spends nothing if nothing new"), **"Full re-scan" warned** ("may use search credits") → `POST /runs` (mutation) → 202 + toast; non-blocking. **Live polling:** `useRuns` `refetchInterval:(q)=> any running ? 2000 : false` (v5 idiom) — running→success flips live, no refresh. **Post-run refresh:** on a run turning terminal, invalidate prospects+stats so the dashboard updates. **Live-verified:** 3 real runs render (dark+light); Run now Both/incremental → no-op completes billed=0/rows=0 shown correctly (0 new geos confirmed free first, no quota spent); count 3→6 resolving live without refresh; Last Run card updated to Jul 1 2026. **324 backend tests** (unchanged), pyright 0, ruff clean; frontend tsc+build+oxlint clean; API/CLI/master Sheet unchanged. Gotcha: no-op finishes ~5s (faster than a screenshot) so the transient running spinner isn't freeze-frameable — verify via live count increment + auto-resolution. **UI COMPLETE (prospects + runs + trigger). Remaining: Phase D (auth), Phase E (hosting).**
- Session 16 (2026-06-30): **SaaS Phase C1-Redesign — product identity + dashboard + export (ADR-016).** Deliberate overhaul of the C1 UI into a real product, plus export. Data already correct; presentation upgraded. Pipeline/DB/API auto-write untouched; UI talks only to the API. **Identity:** named **AuthorityScout** + radar logomark; app shell (slim sidebar — logo, nav Prospects/Runs·soon/Settings·soon, health, theme toggle — + topbar with domain search + export actions). **Dark-first theming:** CSS-variable token system (teal brand, semantic surface/border/fg/trust tokens via Tailwind v4 `@theme inline` + `@custom-variant dark`), light toggle persisted (no-flash init). **Dashboard:** 5 crafted stat cards from a new **`GET /stats`** (total/high-trust/with-email/geos/last-run; tested vs real Postgres). **Table:** client-side sort (ranked trust/confidence, numeric population, competitor count) + Columns visibility menu (Website frozen); polished badges/states. **Export:** CSV (client-side, pages all matching rows) + **`POST /export/sheet`** — a plain SA can't create standalone spreadsheets (Drive 403) so it adds a NEW TAB to a workbook it can edit (`EXPORT_SHEET_ID`, default master) and returns its `#gid` URL; the auto-write tab (Sheet1) is never touched; success toast. **Drawer:** actionable (copy + mailto/tel, trust rationale, competitor chips). **Live-verified:** dark looks like a product; cards 68/6/74%/5/last-run; table 68 + sort + column-toggle + Trust=high→6; CSV 68 rows; live Sheet export → new tab, master Sheet1 stayed 69 rows untouched (proof tabs deleted after); drawer actionable. **324 backend tests** (318+6), pyright 0, ruff/format clean; frontend tsc+build+oxlint clean; CLI + master auto-write unchanged. Pinned lucide-react ^1.22. Gotchas: SA can't create standalone sheets (use addSheet tab); `/prospects` limit caps at 200 (CSV pages through); restart uvicorn after adding routes (no --reload); kill stale vite (port drift breaks CORS). **Next: Phase C2 (Runs view + Run-now + status polling) on this shell.**
- Session 15 (2026-06-30): **SaaS Phase C1 — the Prospects dashboard (first real UI, ADR-015).** New top-level `frontend/` (Vite + React 19 + TS + Tailwind v4 + TanStack Query v5) — the first product screen, reading LIVE data from the Phase B API over real Postgres. Pipeline/DB/API/Sheet untouched; the UI talks ONLY to the API (typed client in `src/api/` mirroring the backend models). Dense internal-tool aesthetic (zinc/indigo, 13px tabular, Inter): **Prospects table** over `GET /prospects` — Website (frozen col), Specific Page (link), Email, Phone, Contact Trust (colored badge high=emerald/med=amber/low=zinc), Geo, Source (MHD/AH badge), Competitors (flagged count), Population (right tabular), Confidence; sticky header, hover, loading/error/empty states. **Filter bar** (Trust/Source/Level → API query params, active highlight + reset) + **pagination** (limit/offset/total, "Showing X–Y of N"); **row→slide-over drawer** with full prospect (provenance, competitor links, links out). **Live-verified via Playwright** (uvicorn :8000 + vite :5173, dev PG :5433): 68 real rows, Trust=high→6, Source=AH→23, paging 1–50/51–68, drawer (montgomery → samhsa.gov), backend-down → graceful "Backend offline" (not a white screen). 318 backend tests green; frontend tsc+build+oxlint clean. Dev story: `VITE_API_URL` + the Phase B CORS (no proxy). Run: `docker compose up -d postgres` + `uv run uvicorn backend.app:app` + `cd frontend && npm run dev`. Gotchas: TS6 `erasableSyntaxOnly` forbids param-property shorthand; scaffold uses oxlint + Vite 8/TS 6/React 19; Tailwind v4 CSS-first (no config/PostCSS); Vite binds IPv6 localhost (verify with Playwright not curl). **Next: Phase C2 (run history + Run-now + status polling).**
- Session 14 (2026-06-30): **SaaS Phase B — backend API (FastAPI, ADR-014).** New top-level `backend/` app over the Phase A repository + pipeline; pipeline + Sheet untouched. App factory + lifespan (async engine/sessionmaker on `app.state`, disposed on shutdown; startup orphan-sweep), request-scoped `get_session`, env-driven CORS. **Endpoints:** `GET /health` (DB probe), `GET /prospects` (trust/source/geo/level filters + limit/offset + total) & `/prospects/{id}`, `GET /runs` & `/runs/{id}`, **`POST /runs`** — opens a run, returns **202 + run_id**, runs the pipeline in a FastAPI BackgroundTask (opens its OWN session; writes BOTH Postgres + Sheet; finalizes success/failed), reusing the S11 cost-safe `run_incremental` + `max_new_geos`/`max_billed` caps (`incremental` default = no-new-geos → 0 spend; `full` re-runs all known geos, circuit-broken). Repository gained pagination/count/by-id + runs listing; `ingest.persist_prospects` split out (persist under an existing run_id). Pydantic `from_attributes` models expose only scalar FKs (no lazy-load). **Live:** `/prospects`→68, `?contact_trust=high`→6, `?source_tag=AH`→23, paging works; `/runs`→2 newest-first; `POST /runs {both,incremental}`→202, polled `running→success`, **billed=0** / 0 rows (0 new geos, verified by a free sitemap diff first), prospects 68→68. **318 tests** (291 + 27 db/api), pyright strict 0, ruff clean; `run`/`schedule` CLI + Sheet write unchanged. fastapi 0.138.2 / uvicorn[standard] 0.49.0. Endpoints unauthenticated this phase (auth = Phase D). Run: `uv run uvicorn backend.app:app`. Gotcha: a `run --dry-run` verification spent 4 billed searches on an uncached geo (dry-run still bills discovery).
- Session 13 (2026-06-26): **SaaS build begins — Phase A: Postgres foundation (ADR-013).** The repo becomes a single-customer SaaS; a Postgres source-of-truth is added UNDER the proven pipeline (Sheet demoted to an export), nothing broken. New `src/authority_finder/db/` subpackage: SQLAlchemy 2.x async models (`prospects`/`runs`/`geos`; native PG enums; `(website,geo_served)` dedup key now a real `UNIQUE` constraint), **psycopg 3** (one driver for async app + sync Alembic), Alembic migrations, async repository (`upsert_prospect`/`get_prospects(filters)`/`create_run`+`finish_run`/`upsert_geo`/`get_geos`) tested against **real Postgres via testcontainers**, and `db/ingest.persist_pipeline_run` bridging OutputRow→DB. `postgres:16` in docker-compose (host 5433; no baked creds). Opt-in **`run --persist-db`** writes the Sheet AND the DB; `run`/`schedule` unchanged otherwise. **Proof** (5 cached geos, billed=0): 68 prospects in Postgres, runs row recorded, 5 geos, 2nd persist → still 68 (unique constraint = idempotent), `trust=high` filter → the 6 high rows. 297 tests (291 existing + 6 DB). Monorepo: `backend/` (FastAPI, Phase B) + `frontend/` (React, Phase C) reserved as top-level. Pinned: sqlalchemy 2.0.51 / alembic 1.18.5 / psycopg[binary] 3.3.4 / testcontainers 4.14.2.
- Session 12 (2026-06-25): **Population column lit (Census key present).** `CENSUS_API_KEY` added to `.env` (was absent); `CensusClient` verified live against ACS5-2024 — state/county/city all exact (Maryland 6,206,011 / Orange County CA 3,165,820 / Newport Beach CA 83,845). **Fixed a fuzzy-match bug** (`c49ca75`): `palos-verdes` wrongly matched `Palo Verde CDP` (pop 75) at ratio 0.909 → tightened `_FUZZY_CUTOFF` 0.86→0.92 so non-Census neighborhoods are honestly `not_found` (all 5 cached geos are exact, so the live fill is unaffected). Filled the column live: **68/68 rows populated, 0 not_found, billed_searches=0** (Census-only enrichment + `replace`; idempotent append 0). 4 rows web-verified — exact ACS5-2024 figures, right geo (cross-state Springfield trap ruled out via state-FIPS scoping). Sheet reset to the canonical 68 (S11 irvine sim rows dropped). 291 tests. No new ADR (cutoff tweak within ADR-008).
- Session 11 (2026-06-25): **scheduled auto-triggers + Docker (component 8, ADR-012) — MVP COMPLETE.** New `scheduler/` package: `monitor.diff_sitemap` (detect split from persist) + `run_incremental` (process ONLY newly-published geos; persist state only after success, only for processed geos; zero new ⇒ zero spend/writes; crash never marks geos seen) + in-process APScheduler 3.x (`AsyncIOScheduler`, `schedule` CLI, `--once`, `RUN_INTERVAL_HOURS`). **Cost rails:** `MAX_NEW_GEOS_PER_RUN` (25, cap+defer) + `MAX_BILLED_SEARCHES_PER_RUN` circuit breaker (`SerpApiClient(max_billed=…)` → distinct `QuotaExceededError`, `discover_many` re-raises → abort no-save). **Docker:** single-stage py3.12-slim-bookworm + uv + chromium (secrets MOUNTED read-only never baked; `./data` bind-mounted so cache+state persist → no backlog re-processing; config-driven `--no-sandbox`). Live: no-op tick 0/0/0; new-geo sim billed=4 / 12 rows for one geo (not the set); container builds + runs + state persists across restart. 290 tests. **All 8 brief components done; component 3 (Ahrefs authority_filter) intentionally SKIPPED per client (no API).**
- Session 10 (2026-06-24): **competitor backlink detection — `link_checker` (component 6, ADR-011).** New `link_checker/` package (models, `check.find_competitor_links`, `resources.find_resources_link`, orchestrator). Matches on registrable domain (`rehabs.com` ≠ `rehabsomething.com`), resolves relative/scheme-relative hrefs, skips own-domain, dedupes. Mode (b): checks the detected page + ONE resources/links page, ≤2 fetches/candidate. Wired into the pipeline; the previously-blank **Competitor Links** column is now populated (`"; ".join(domains)` / `"—"`), no schema change (idempotency still keyed on Website+Geo; value refresh via `replace`). Live: 0 billed, 484 fetches (364 httpx/75 pw), **8/68 rows link to a competitor (11 links: samhsa.gov ×8, findtreatment.gov/addictioncenter.com/treatmentatlas.org ×1)**; replace 68 + idempotent 0; 4 flagged Playwright-verified (0 false positives) + 2 clean verified (no under-detection). 282 tests. Recall limits: JS-injected links, deep pages, `MAX_LINKS=500` cap.
- Session 9 (2026-06-24): **contact quality — diagnose, then lift (ADR-010).** Diagnosed first (`docs/contact-quality-audit.md`): page detection strong, attribution weak, ranker not mis-picking (bucket B=0), and **23/68 rows (34%) publish no same-domain email — the structural ceiling**. Built **department-directory discovery** (hop fires unless a same-domain dept inbox is already held; dept/directory/MH-topic links ranked over generic contact-us; dept inbox ranks first), a single evidence-derived `classify_localpart` (dept/role/generic/other, with an `environmental`/`developmental` guard), and **re-derived the trust bands — TIGHTENED**: role/wrong-dept→`low` even as same-domain mailto, generic `info@`→`medium` (never `high`), dept same-domain mailto→`high`. Plus a phone-glue email guard. Live re-run: 0 billed, `replace` rewrite 68 + idempotent append 0; **trust high 1→6 / medium 27→18 / low 40→44** (high+medium drops 28→24 — the old mediums over-counted wrong-dept inboxes; quality up, not down). 6 high rows Playwright-verified on same-domain dept pages. 262 tests.
- Session 8 (2026-06-23): **contact attribution hardening (ADR-009).** Body-text emails domain-constrained to the candidate's registrable domain (`EmailHit.same_domain`); page-detection `Confidence` split from a new **Contact Trust** band + **Contact Source** provenance column; cross-domain mailto (e.g. the live `info@frsn.org` third-party case) flagged "mailto (off-domain)" / `low` rather than shown as trusted; ucdenver `admissions@` → `low`. Sheets `replace` mode added for value-correction full refresh. Live re-run: 0 billed, migration + idempotency clean, trust distribution high 1 / medium 27 / low 40. 228 tests.
- Session 7 (2026-06-19): **Phase 1 MVP COMPLETE + live Sheet verified.** `population/` (ACS5-2024 keyed Census lookup — keyless retired ~May 2026 → free key required, degrades to not_found without one) + `output/` (brief-exact row schema, CSV writer, idempotent Google Sheets writer) + `pipeline.py` + `run` CLI (full chain → CSV `--dry-run` or live Sheet). ADR-008. **Live close:** leaked `service-account.json` (committed S6) was purged from git history AND the key was rotated in GCP (gate verified `private_key_id` changed); live run over the 5 cached geos wrote **69 rows to the Google Sheet at 0 billed searches**, idempotent re-run appended 0, no fabrication. Population blank (no `CENSUS_API_KEY` yet). Known limitation: body-text contacts can be a third-party org referenced on the page (Phase 1.x: domain-constrain body-text emails/phones). `google-api-python-client==2.197.0`, `google-auth==2.55.0`.

## What does `run` do

`python -m authority_finder.cli run --site {mhd|ah|both} [--limit N] [--level …] [--dry-run] [--out FILE]` — the product. Chains monitor-state → discover (SerpAPI, cached) → detect → extract → populate (Census) → assemble brief-column rows → write CSV (`--dry-run`) or append to the Google Sheet (idempotent, dedupe by domain+geo). Per-geo isolation; prints a funnel summary.

## Status: MVP COMPLETE (Phase 1 + Phase 2)

All brief components are shipped except component 3 (Ahrefs `authority_filter`), which is
**intentionally out of scope per the client (no Ahrefs API)** — not missing:
- ~~`link_checker` (component 6)~~ — **DONE (S10, ADR-011):** competitor backlink detection; Competitor Links column populated.
- ~~Scheduled auto-triggers + Docker (component 8)~~ — **DONE (S11, ADR-012):** `schedule` CLI / Dockerized scheduler; cost-safe incremental runs.
- `authority_filter` (component 3) — **SKIPPED (client decision, no Ahrefs API).** If revived: needs unrestricted query variants since `site:`-filtered discovery can't surface ncala.org-type orgs.

Operational follow-ups (not code): pick a cloud host (Docker-ready — `docker compose up -d`); add a free `CENSUS_API_KEY` to light up Population; show Jake.

How to run it: `python -m authority_finder.cli run …` (one-off, below) or `python -m authority_finder.cli schedule` / `docker compose up -d` (continuous — see README). The backend API (Phase B): `uv run uvicorn backend.app:app` (needs Postgres up — `docker compose up -d postgres`; reads the same `.env`; OpenAPI at `/docs`).

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
