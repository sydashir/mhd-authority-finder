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

---

## 2026-05-22 — Session 3: geo_monitor end-to-end

### Done

- Re-read `CLAUDE.md`, `docs/brief.md`, `docs/sites.md`, `docs/architecture.md`, `docs/decisions.md`.
- **Cleanup commit:** removed dead `HUNTER_API_KEY` field from `config.py` + `.env.example`, scrubbed Hunter.io mentions from `CLAUDE.md` module-layout block and Phase 1 next-steps, rewrote `contact_extractor.py` docstring. (Walks back ADR-003's "keep as dead placeholder" sub-clause; ADR-003 is append-only so the walk-back lives here and the contradicting Settings field is gone.)
- **New deps pinned:** `tenacity 9.1.4`, `lxml 6.1.1`, `click 8.4.1`, `playwright 1.60.0`, `types-lxml 2026.2.16`.
- Converted `geo_monitor.py` stub into a full `geo_monitor/` package with eight modules:
  - `models.py` — pydantic v2 `SiteConfig`, `GeoPage`, `SitemapEntry`, `MonitorRun`, `MonitorError`, `SiteState`. `SiteConfig` stores a compiled `re.Pattern` (`arbitrary_types_allowed=True`, frozen). No `from __future__ import annotations` because pydantic v2 needs runtime-resolvable types.
  - `states.py` — `US_STATE_SLUGS` frozenset of 50 hyphenated state slugs.
  - `sites.py` — `MHD` + `AH` `SiteConfig` instances + `SITES` lookup dict.
  - `sitemap_fetcher.py` — `SitemapFetcher` class. `httpx.AsyncClient` injection, `asyncio.Semaphore(2)` per-host concurrency cap, `tenacity.AsyncRetrying` with exponential backoff on 5xx and network errors, `urllib.robotparser` check cached per host, lxml parsing against `http://www.sitemaps.org/schemas/sitemap/0.9` namespace, ISO 8601 `<lastmod>` parsing via `datetime.fromisoformat`. Custom `RobotsDisallowedError`.
  - `url_parser.py` — pure `parse_geo_url(url, config, *, now)` function. Regex match → state-slug whitelist → level inference → URL normalization (trailing slash added, query + fragment stripped).
  - `state.py` — `data/state/{site_id}.json`. Atomic write via `.tmp` + `os.fsync` + `Path.replace`. Load-missing returns empty `SiteState`. Orphan `.tmp` files are ignored by `load_state` — the canonical file stays canonical.
  - `monitor.py` — `run_monitor(config, *, fetcher)` orchestrator. Load state → fetch geo entries → parse → diff against `known_urls` → save union → return `MonitorRun`. Per-site error isolation is the CLI driver's job.
- **CLI:** `python -m authority_finder.cli monitor --site {mhd|ah|both} [--json]`. Click-based. One `SitemapFetcher` per site (independent semaphores) sharing one `httpx.AsyncClient`. `asyncio.gather(return_exceptions=True)` for per-site isolation. Exit 1 only when every requested site errored.
- **Tests** (42 unit + 5 live, all green):
  - `tests/geo_monitor/test_url_parser.py` — 33 cases. MHD + AH state/county/city, trailing-slash variants, query/fragment stripping, multi-word state slugs, AH non-geo rejection (`/about`, `/contact`, `/services`, `/blog`, `/treatment-programs`), uppercase rejection, deep-path rejection.
  - `tests/geo_monitor/test_state.py` — load-missing returns empty, save+load roundtrip, orphan-`.tmp` does not corrupt load, nested state directory creation.
  - `tests/geo_monitor/test_models.py` — pydantic validation edge cases including JSON round-trip of `MonitorRun` and set-based `SiteState.known_urls` serializing as list.
  - `tests/geo_monitor/test_sitemap_fetcher_live.py` — hits real MHD + AH sitemaps. Asserts index returns sub-sitemaps and all parsed entries have valid state slugs.
  - `tests/geo_monitor/test_sitemap_verification.py` — Playwright chromium sample verification (see below).
- Registered `live` pytest marker; default `pytest` deselects it via `addopts = ["-m", "not live"]`. Opt in with `pytest -m live`.
- ADR-004 written — state-slug whitelist strategy with explicit alternatives table.
- `README.md` updated with `uv run playwright install chromium` setup step.

### Playwright verification findings (session 3 sample)

Sample seed: **42**. Six URLs verified (3 MHD + 3 AH). One headless chromium instance, 15s nav timeout per URL.

- **6/6 clean.** All returned HTTP 200, no redirects to homepage, expected geo slug appeared in `<title>` or `<h1>`.
- Sampled URLs:
  - MHD: `/serving/california/orange-county/newport-beach/` (city)
  - MHD: `/serving/florida/` (state)
  - MHD: `/serving/california/los-angeles/palos-verdes/` (city — note MHD treats `los-angeles` as the county-level slug here)
  - AH: `/maryland/`, `/alabama/`, `/virginia/` (all state)
- Detailed per-URL findings persisted to `data/playwright_findings.json` (gitignored).
- **No sitemap drift observed this run.**

### Discovery counts (fresh state, both sites)

```
site    total   new  state  county  city
------------------------------------------
mhd        23    23      2       4    17
ah         49    49     49       0     0
```

Notable: AH's live sitemap has only state-level geo pages right now. The site's documented URL pattern allows `/{state}/{county}/{city}/` but no county/city pages are published yet. The fetcher + parser are correct for those URLs when they appear — covered by the unit tests — but we won't see them in production output until the client publishes them.

### Decisions made this session

- **ADR-004** — state-slug whitelist for geo URL disambiguation.
- **Walk-back of ADR-003 sub-clause:** Removed `HUNTER_API_KEY` from `Settings` + `.env.example` instead of keeping it as a placeholder. The "kept for future migration" rationale is weaker than the cost of having a dead config field that contradicts the rest of the docs.
- **AH regex matched 68, parser kept 49.** 19 URLs (`/about/`, `/contact/`, `/blog/`, `/services/`, `/treatment-programs/`, etc.) hit the loose AH regex but failed the state-slug whitelist. This is exactly what ADR-004 exists to handle — working as designed. The fetcher returning more than the parser keeps is a deliberate separation of concerns; the fetcher knows URL shape, the parser knows geo semantics.
- **Each site gets its own `SitemapFetcher` instance** (independent `Semaphore(2)`s) sharing one `httpx.AsyncClient` (single connection pool). MHD being slow can't starve AH.
- **`run_monitor` takes `fetcher` as a kwarg** (vs. constructing inside) — needed for testability and to share clients across sites. Not in the original brief signature; small deviation flagged here.
- **Stub-to-package conversion** for `geo_monitor` happened transparently — the original `geo_monitor.py` stub was deleted in the data-models commit. Module layout in `CLAUDE.md` still says `geo_monitor.py`; will update next session when we touch it again.

### Sitemap drift / quality observations

- Both sites' `robots.txt` is permissive — no `Disallow` rules blocking the sitemap or any geo path.
- MHD splits geo pages across `/page-sitemap.xml` only (the index lists 3 sub-sitemaps but only one contains pages).
- AH same — 2 sub-sitemaps in the index, geo pages live in `/page-sitemap.xml`.
- Neither site emits `<lastmod>` consistently. The fetcher accepts missing `<lastmod>` and leaves it `None`.
- AH publishes only state-level pages right now (49 of them). MHD has full state/county/city depth (2 / 4 / 17).

### Open questions for the user

1. **AH county/city pages.** AH's documented URL pattern supports `/{state}/{county}/{city}/` but only state pages exist in the sitemap as of this run. Is the client planning to publish county/city for AH? Affects whether downstream pipeline steps should warn when AH outputs are state-only.
2. **MHD has `/serving/california/los-angeles/palos-verdes/`** — Los Angeles is a county AND a city. MHD's URL hierarchy slots LA into the county position. Treating it as a county-level geo for outreach is probably correct (county health dept, etc.) — confirm?
3. **State pages vs. city pages for outreach.** A state-level geo (`/maryland/`) covers all of Maryland. Do we want different discovery queries for state-level (state health dept, state board) vs city-level (city health dept) outreach? Affects Session 4's `discovery` component design.

### Blocked

Nothing blocked. Phase 1 next step (`discovery`) can start immediately.

### What's next — Session 4

`discovery` component:
- SerpAPI client wrapper (or Google Custom Search — still unanswered, will flag at session start).
- Per-geo query construction: combine geo level + slugs into search queries that target `.gov` and `.edu`.
- Result post-processing: domain dedup, suffix filter.
- Tests: unit (query construction) + live (one real geo → real search → assert at least one `.gov` candidate).

Open before Session 4:
- SerpAPI vs Google Custom Search — API key needed.
- Query template strategy: one query per geo level, or multiple queries with different keywords combined? Decision call before code.

---

## 2026-06-12 — Session 4-prep: resync + health audit (no feature code)

### Done

- **Session journal rule installed** (`fcf135d`): mandatory self-triggered journal rule appended to `CLAUDE.md` working rules; `journal/` created and gitignored (no `.gitkeep` — it would defeat the gitignore). First journal entry written: `journal/SESSION-2026-06-12-resync-health-audit.md` + `journal/INDEX.md`.
- **SessionStart hook wired** (`b471a77`): current Claude Code has **no PreCompact hook event** (verified against live hooks docs 2026-06-12). The committed `.claude/settings.json` registers a `SessionStart` hook (fires on startup/resume/**compact**) running `.claude/hooks/session-start-journal.sh`, which injects the latest journal filename as context. Pre-compaction journal *writes* cannot be hook-automated — they rely on the CLAUDE.md rule.
- **ClickUp cross-check** (task `86b9re44b`, read-only): first comment matches `docs/brief.md` verbatim — no deltas. Latest client comment (2026-05-12): not urgent, **MVP target end of July 2026**.
- **Git history audit**: all 19 pre-session commits map cleanly to Sessions 1–3 in this log. No unaccounted commits in either direction.
- **Toolchain audit — all green, zero fixes needed**: uv 0.11.15, `uv sync` clean (37 pkgs), `ruff check` pass, `ruff format --check` pass, `pyright` strict 0 errors, 42 unit tests pass. Playwright chromium 148.0.7778.96 launches. Global attribution settings intact (`commit: ""`, `pr: ""`). (Note: pyright 1.1.410 available vs pinned 1.1.409 — bump deliberately, not now.)
- **Live verification**: `pytest -m live` 5/5 pass (31.8s). CLI `monitor --site both`: MHD 23 total / **0 new**, AH 49 total / **0 new** — exact match with Session 3 baseline, stateful diff working (state files: counts unchanged, `last_run` bumped).
- **Sitemap drift check**: AH index now lists 3 sub-sitemaps (was 2 in Session 3) — new `local-sitemap.xml` contains only `locations.kml` (Rank Math local SEO; MHD has the same). Benign: no geo pages outside `page-sitemap.xml`, fetcher's `page-sitemap` filter behaves correctly. No geo URL drift → Playwright sampling not triggered.
- **Library research (context7 + web, for Session 4 discovery build)**:
  - httpx 0.28.1 = latest stable; pin safe. Use `follow_redirects=True` explicitly, avoid `http2=True`, raise the 5s default timeout for .gov sites.
  - tenacity 9.1.4 = latest; pin safe (includes async `sleep=` typing fix relevant to strict pyright).
  - SerpAPI: official `serpapi` PyPI client (v1.0.2) is **sync-only** → call `GET https://serpapi.com/search.json` directly with httpx. `q` supports `site:` operators. **`num=100` is dead on `engine=google` (since Sept 2025)** — ~10 organic results/request paginated via `start`, or `engine=google_light_fast` supports `num=100` (organic results only). Response: `organic_results[]` → `position/title/link/snippet`. Handle 429 with backoff; hourly throughput caps per plan.

### Observations / risks flagged

- `sitemap_fetcher.py:86` sub-sitemap selection (`"page-sitemap" in u`) is load-bearing: geo pages published to a differently-named sub-sitemap would be silently missed. Consider logging skipped sub-sitemap names in Session 4.
- `CLAUDE.md` "Current state" + module-layout sections still describe Session 1 (stubs, `geo_monitor.py` as a file). Known-stale since Session 3; out of this session's allowed-commit scope. Refresh as first commit of Session 4.

### Open questions (blocking Session 4)

1. SerpAPI vs Google Custom Search — decision + API key. If SerpAPI: plan tier and engine choice (`google` paginated vs `google_light_fast`).
2. Query strategy per geo level (state vs county/city) — Session 3 Q3, still unanswered.
3. (Non-blocking for discovery) Google Sheet ID + service-account credentials for `output.py`.

### What's next — Session 4

`discovery.py` per the Session 3 plan, grounded in the SerpAPI findings above: async httpx client for `search.json`, per-geo query construction, domain dedupe + `.gov`/`.edu` suffix filter, unit tests on query construction + fixture-based response parsing, one live test per real geo.

---

## 2026-06-13 — Session 4: discovery engine (SerpAPI .gov/.edu search per geo)

### Done

- **Housekeeping:** CLAUDE.md refreshed to post-Session-3 reality + `sydashir` gh-account note (`8d58bd5`); fetcher now logs each skipped sub-sitemap with reason, with a MockTransport unit test proving non-page sitemaps are never even fetched (`7879260`).
- **Step-2 validation killed the prep-research plan:** `google_light_fast` retired by SerpAPI (HTTP 400, unbilled), and **no Google engine supports `num` anymore** — ~10 organic results = 1 billed search, period. Stopped per session rules; user picked **`google_light`, page 1 only** (depth stays a client knob). Real validation call captured as the unit-test fixture (`tests/discovery/fixtures/google_light_california.json`) — 10/10 results with `position/title/link/snippet`.
- **`discovery/` package built** (stub → package, like geo_monitor in Session 3):
  - `models.py` (`f8715b1`) — `GeoRef` (slim geo ref), `SearchResult`, `CandidateSite`, `DiscoveryError`, `DiscoveryResult` with `counts_by_class` measuring dropped classes.
  - `serpapi_client.py` (`c1b2016`) — async httpx GET on `search.json`; tenacity retry (3 attempts, exponential, Retry-After honored on 429); disk cache `data/cache/serpapi/{sha256}.json` keyed on params-minus-api_key; `billed_search_count`/`cache_hit_count` session counters; billed searches logged with running total.
  - `queries.py` (`5854f11`) — locked-theme templates per level (4 state / 3 county / 4 city); slug→display conversion; **county-suffix normalization** (MHD slugs are inconsistent: `orange-county` vs `los-angeles` — without stripping, templates would produce `"Orange County County"`).
  - `classify.py` (`e339e64`) — tldextract 5.3.1 (offline PSL snapshot, pyright-strict clean); gov/edu/us_local/other; **state-portal dedupe exception** (user-confirmed): PSL has no `.gov` entries so `dhcs.ca.gov` + `mentalhealth.ca.gov` both have registrable domain `ca.gov` — portals keep one non-www label so agencies stay distinct rows.
  - `discover.py` (`96ce2e8`) — per-query error isolation (errors are result data), `discover_many` with `Semaphore(2)` + per-geo isolation (failed geo → empty result carrying the error).
  - CLI `discover` (`f770d4e`) — `--site/--limit/--level/--refresh/--json`; geos sourced from `data/state/*.json` re-parsed through the URL parser; per-geo table with class counts + billed/cached; exit 1 only if every geo errored; exit 2 if no API key.
  - Tests (`058295d`) — 34 new unit tests (queries, classify, client cache/retry/errors, orchestrator vs the real fixture; zero network in units); new **`live_paid` marker** registered, excluded from default AND from `-m live`; one paid smoke test (passes, 1 billed search).
- **ADR-005** (`0ce2934`) — engine choice, direct-httpx integration, no-TTL dev cache, classification + dedupe policy, quota guard pattern.
- **Live validation (19 billed searches):** `/maryland/`, `/colorado/` (AH state), `/serving/florida/` (MHD state), `/serving/california/orange-county/` (county), `.../newport-beach/` (city) → 127 candidates (gov 86 / edu 41 / us_local 0 / other 0). Full results in `data/discovery_validation.json` (gitignored).
- **Playwright spot-checks 3/3 pass** (one per level): `health.maryland.gov/bha/pages/help.aspx` (200, "Get Help"), `bos4.oc.gov/mental-health-resources` (200, exact match), `newportbeachca.gov/government/departments` (transient Cloudflare 522, 200 with correct title on retry).
- **Quota: 21 of 40 billed searches used** (1 fixture + 1 live_paid test + 19 validation); 0 retries billed.

### Live-quality assessment (evidence for Session 5)

- **Bullseyes:** `bha.colorado.gov` #1 for Colorado; `health.maryland.gov/bha` + `dpscs.maryland.gov` substance-abuse program (probation theme works); `floridahealth.gov`; `bos4.oc.gov/mental-health-resources`; `newportbeachca.gov`; university counseling centers throughout (`counseling.umd.edu`, `colorado.edu/counseling`, `counseling.ufl.edu`).
- **Bonus:** state-level queries pre-surface county health departments (5 MD counties, 6 CO counties) — future geo pages get a head start.
- **Junk patterns (page-detector TODO list):** (1) national/federal domains everywhere — `samhsa.gov` + `findtreatment.gov` (both on the client's 16-competitor list!), `medicare.gov`, `cms.gov`, `nih.gov`, `va.gov`, `cdc.gov` — need a federal blocklist or geo-scoring; (2) same-name wrong-state geos — `orangecountync.gov`, `orangecountyva.gov` for Orange County CA, `cga.ct.gov` in Florida results, `natickma.gov`/`greenfieldca.gov` in Colorado; (3) PDFs (~8 results); (4) news/press/blog pages on .gov/.edu; (5) search-results/listing URLs. City-level is noticeably noisier than state/county.
- **`us_local` = 0 across all 127:** modern county/city sites have moved off `.us` onto `.gov` (`oc.gov`, not `co.orange.ca.us`). Classification stays (zero cost) but `.us` is not where the value is.
- **`other` = 0 — structurally:** `site:`-restricted queries can never surface ncala.org-type authority orgs. The drop-but-count instrumentation works; it measured that *these queries* drop nothing. Phase 2 needs unrestricted query variants + Ahrefs DR, not just a filter on current results.

### Decisions this session (full rationale in ADR-005)

- `google_light` page-1-only (user-confirmed after `google_light_fast` retirement).
- State-portal dedupe exception (user-confirmed; strict registrable-domain dedupe observably lost fixture positions 1–2).
- County-slug suffix normalization in the query builder (evidence: real MHD slugs).
- `live_paid` marker kept disjoint from free `live` marker.

### Open questions

1. **National-domain handling for Session 5:** blocklist (samhsa/medicare/cms/nih/va/cdc/findtreatment...) vs geo-relevance scoring in the page detector? (findtreatment.gov + samhsa.gov are competitor domains, not outreach targets — they should arguably be excluded from candidates entirely.)
2. **Wrong-state same-name geos** (Orange County NC/VA): page detector needs a state-validation signal (state name on page / in domain). Confirm this lands in Session 5 scope.
3. Google Sheet ID + service-account credentials — now the next external blocker (`output.py`).

### What's next — Session 5

`page_detector`: score candidate URLs/pages for "is this the right department page for this geo" — keyword scoring + the junk-pattern filters above (federal blocklist, state validation, PDF/news down-ranking), low-confidence flagging for manual review.
