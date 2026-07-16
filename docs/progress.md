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

---

## 2026-06-13 — Session 5: department page detector

### Done

- **Shared constants** (`b4813ad`): package-level `domains.py` — `COMPETITOR_DOMAINS` (the brief's 16, reused by Phase 2's link checker) + `FEDERAL_DOMAINS` (39 curated), registrable-domain matching via tldextract.
- **`page_detector/` package** (stub → package): models (`5d0f024`), pre-filter (`97146dc`), polite HTML fetcher (`95a6030`), explainable scorer (`84ad0fa`), bounded crawl fallback (`cc46686`), orchestrator (`8613284`), `detect` CLI with `--in/--out` chaining + `--out` on `discover` (`bbbf7d8`).
- **Robots checker extracted** to shared `robots.py` (`c7d5bd4`) — geo_monitor and page_detector now share one politeness implementation + USER_AGENT.
- **Three bugs found BY live validation, fixed, regression-tested:**
  1. `fix: reject off-domain redirects in detector` (`c05cf85`) — `greenfieldca.gov` + `natickma.gov` are redirect shells 301ing to **palmerlakerecovery.com** (private rehab company); it scored 8.5/high under a .gov label before the fix. Final URL must now stay on the candidate's registrable domain.
  2. `fix: catch prefixed news paths in junk filter` (`bf871bb`) — `westcliff.edu/wu-news/` evaded the `/news/` segment check.
  3. `fix: cap confidence at low without topic relevance` (`efc3919`) — an "Animal Services" page cleared medium on services+locality+contact; pages with no topic keyword anywhere (title/path/body) are now capped at low; body-only topic earns +0.5 `topic_in_body` and escapes the cap (health.maryland.gov/bha is titled just "Get Help").
- **Tests** (`6e357da` + fix commits): 41 page_detector tests — pre-filter branches, every scorer signal, wrong-state, banding, crawl budget (exact 6-fetch ceiling), content-type/size guards, robots, plus 3 real-HTML regression fixtures captured live (montgomerycountymd, coloradocollege, bos4.oc.gov). Suite: 118 unit tests, zero network.
- **ADR-006** (`8f131aa`) — exclusion policy, explainable-rules-over-ML, crawl budget, confidence bands + the two post-validation policy additions.

### Live validation (127 candidates, 5 cached geos, 0 SerpAPI calls, 172 page fetches)

- **Status:** 54 detected / 38 rejected / 35 fetch_failed. **Confidence:** 23 high / 21 medium / 10 low.
- **Rejections, named:** 23 federal (medicare, cms, nih, va, cdc, hhs, fda, justice, ojp, ed, uscourts, ussc, house, medicaid); 7 competitor — **samhsa.gov and findtreatment.gov excluded everywhere they appeared**; 3 wrong_state — **orangecountync.gov and orangecountyva.gov both rejected for the Orange County CA geo**, plus greenfieldca.gov (Greenfield CA homepage, for the Colorado geo); 2 junk_url; 3 no_viable_page.
- **Top picks (per geo):** MD `montgomerycountymd.gov/...mental-health-resources-public-safety` + `cityoffrederickmd.gov/1753/Mental-Health-Resources`; CO `coloradocollege.edu/.../mental-health-resources.html`, `colorado.edu/counseling/`, `cuanschutz.edu/mental-health-resources`; FL `dasa.fiu.edu/.../counseling-and-psychological-services/`, `usf.edu/.../mental-health-resources.aspx`; OC `bos4.oc.gov/mental-health-resources` (11.0, the run's best), `ocsheriff.gov/.../behavioral-health`; NB top pick is an honest miss (below).
- **Playwright spot-checks:** 5 per-geo top picks all HTTP 200 with content as scored; 4/5 are right-org outreach pages. The Newport Beach top pick (`longbeach.gov` "Environmental Health: Additional Resources") is a confirmed miss — "substance" matched on hazardous-substances content and Long Beach ≠ Newport Beach.
- **Blind accuracy sample (seed 42, 20 of the 44 high+medium):** judged harshly — right org AND right page AND right geo. **High: 8/8 (100%). Medium: 5/12 (42%). Overall: 13/20 (65%)** vs the feasibility doc's 70–75% promise. Read: ship high as auto-accept, medium as light review, low as full review — that beats the promise where it matters. Medium misses cluster on: generic single body keywords escaping the topic cap ("treatment" on an animal-services page, "recovery" on a generic city services page), facility/location pages, press releases with `pr-` prefixes, and city-level geo mismatches (a college one town over).
- **Fetch failures = 27% of candidates, dominant mode: 403 bot-blocking of our honest UA** (bha.colorado.gov, cdphe.colorado.gov, floridahealth.gov, baltimorecountymd.gov, counseling.umd.edu, counseling.fsu.edu...) plus one SSL-chain failure (cdph.ca.gov). These are some of the *best* orgs — state health departments behind enterprise WAFs. fmu.edu even 403s headless Chromium.

### Decisions this session (rationale in ADR-006)

- Competitor/federal exclusions, rule-based scoring, 6-fetch crawl budget, confidence thresholds (user-locked scope + post-validation refinements).
- Re-running detection after fixes instead of patching data: three polite passes over ~90 hosts (~6 fetches/host total across hours).

### Open questions for Session 6 (contact extractor)

1. **The 403 wall.** 27% of candidates — including state health departments — block our honest UA, and the contact extractor will hit the same wall. Options: (a) accept and flag; (b) Playwright-fetch fallback tier for 403s (real browser, still robots-respecting); (c) browser-like UA string (effective but less honest). Decision needed before Session 6 — recommendation: (b).
2. **Medium-band tuning**: the 20 judged samples are the seed of a labeled corpus; tune `W_TOPIC_BODY`/resource-marker genericity against it before promoting medium to auto-accept.
3. Contact affordances observed while fetching: mailto/tel present on ~half the detected pages (`contact_affordance` signal fired on most high scorers) — direct-scrape coverage for Session 6 looks promising on .gov; .edu counseling pages lean on contact-form links.
4. Google Sheet ID + service-account creds — still the external blocker for `output.py`.

### What's next — Session 6

`contact_extractor`: email + phone from detected pages (direct scrape per ADR-003) — mailto/tel parsing, obfuscation patterns, contact-page hop (reuse the crawl machinery), per-page provenance for the sheet. Resolve the 403-fallback question first.

---

## 2026-06-17 — Session 6: contact extractor + shared two-tier fetch

### Done

- **Shared `fetching/` tier** (`db9898d` refactor, `a9a86ab` playwright): promoted `page_detector/fetcher.py` to `authority_finder/fetching/` (both detector and extractor import it). httpx first, always; escalate to headless Playwright Chromium only on 403 or TLS-chain failure (genuine browser UA, not spoofed httpx headers); robots enforced before either tier; ≤1 browser fetch/URL; one lazily-launched reused browser; hard-403-after-browser → fetch_failed. `PageContent` gained `mailto_links`/`tel_links`/`has_web_form`/`fetch_tier`. `playwright` promoted dev→runtime dep.
- **`contact_extractor/`** (models `e381b77`, extract `5774914`, contact-page `36edec6`, orchestrator `0995156`, CLI `54c5f3e`): `phonenumbers==9.0.32` via `PhoneNumberMatcher`; vetted email regex + guards (NOT email-validator — DNS-by-default, validates-not-extracts); mailto/tel first, body-text + obfuscation decode; confidence + trust-order ranking; ≤2 same-domain contact-page hops when no email; `extract` CLI chains from detection JSON or runs discover→detect→extract internally.
- **Adversarial audit (5-lens Workflow) → 5 fix commits.** Each lens generated messy inputs and ran them against the real functions; reproduced defects fixed + pinned as regression tests:
  - `cc86ef8` phone: EXACT_GROUPING + reject pure-digit raws + record-label guard (killed order/invoice/confirmation/case/account-number false positives that ALL leniency levels accepted).
  - `23afe9a` email FP: template-token strip (`{{}}`/`${}`), placeholder-domain **suffix** match (Sentry DSN subdomains), non-PSL-TLD reject (tldextract), numeric-domain-label reject (version pins), code-ext blocklist.
  - `d415df2` multi-segment spelled obfuscation (`info at mail dot county dot gov` was truncating to a *wrong* address; now decodes whole, incl. county `.us`).
  - `342d1a5` email ranking: trust-order tie-break (mailto > contact_page > body_text) + case-insensitive dedupe.
  - `df2d9ea` (from live quality sample): reject 5+ digit local-part runs (ZIP/phone glued into the address with no separator).
- `2a993ef` **concurrency fix found by the live run**: `_ensure_browser` raced under concurrent escalations and launched 7 browsers (orphaning 6); fixed with a double-checked async lock. Re-validated: extraction run launched exactly 1.
- Tests `9bff2c7`: 53 contact-extractor unit tests + 6 two-tier fetch tests; suite now 181 unit tests, zero network. ADR-007 `d91dd33`.

### Live validation (5 cached geos, 0 SerpAPI calls)

**Part A — Playwright recovery:** of Session 5's **35** fetch-failures, **14 recovered (40%)** — incl. floridahealth.gov, cdph.ca.gov (SSL-chain, browser tolerates the missing intermediate), fsu.edu, umd.edu, fmu.edu (403'd even headless Chromium in S5, loads via nav flow now), umbc.edu, unco.edu, pinellas.gov, ocauditor.gov, 5 more. Detected pages 54→67. Detection fetches: 118 httpx + 24 playwright. **21 still fail** (enterprise WAF/timeout: bha.colorado.gov, cdphe.colorado.gov, baltimorecountymd.gov, virginia.edu…) — graceful degradation.

**Part B — extraction coverage (67 detected pages, 107 fetches: 86 httpx + 18 playwright):**
- Email: **49/67 = 73%** — .gov **22/31 (70%)**, .edu **27/36 (75%)**.
- Phone: **54/67 = 81%** — .gov **26/31 (83%)**, .edu **28/36 (77%)**.
- Form-only: **0** (every page yielded email/phone or nothing — the Session-5 ".edu leans on contact forms" worry didn't materialize; the contact-page fallback closed the .edu gap, and .edu email edged out .gov).
- fetch_failed during extraction: 2.
- Both above the feasibility doc's 65–75% promise.

**Quality sample (15 random extracted emails, judged harshly = department-relevant + usable for THIS geo's outreach):** ~8/15 usable. Clearly good: recoverysupport@howardcountymd.gov, bhs@frederickcountymd.gov, chhsmail@chhs.ca.gov, fourth.district@ocgov.com, ivccounseling@ivc.edu. Borderline-usable (real institutional/person inbox): info@csupueblo.edu, jsilverman@umaryland.edu, mallee@ndm.edu. Misses: mdmanual@maryland.gov (archives, not BHA), newsmedia@flhealth.gov (press), bcso@bouldercounty.gov (sheriff), servicedesk@chapman.edu + csinfo@bu.edu (IT/CS — the bu.edu page was a Session-5 mis-detection), cccadmissionsoffice@coastline.edu (admissions). One garbled hit (#7, ZIP+phone glued) → fixed by `df2d9ea`.

**Playwright spot-checks:** 3/3 — recoverysupport@howardcountymd.gov, fourth.district@ocgov.com, chhsmail@chhs.ca.gov — extracted email AND phone confirmed present on the live page (no hallucination).

### Decisions this session (rationale in ADR-007)

- Two-tier httpx→Playwright fetch (user-resolved 403 policy); genuine browser, no UA spoofing.
- phonenumbers for phones; regex+guards (not email-validator) for emails.
- All audit/validation-driven precision guards above; precision-over-recall throughout.

### Failure modes, honestly

- **Email misses cluster on wrong-but-real inboxes** the extractor can't distinguish from dept contacts: press/news, IT helpdesk, admissions, archives, sheriff. These are correctly *extracted* (real addresses on the page) but are the wrong *department* — page-relevance, not extraction, is the lever (a future refinement could score local-part vs the page's topic). Two were downstream of Session-5 page mis-detections (bu.edu CS page).
- **21 hosts still 403/timeout even via Playwright** — enterprise WAFs (Akamai/Cloudflare bot-management) that block headless Chromium too. Flagged, not chased.
- Role/generic inboxes (info@, servicedesk@) rank below dept inboxes but still surface when nothing better exists — by design.

### Open questions for Session 7

1. **Phase 1 remaining = population (Census, component 7) + Google Sheets output (component 8).** Census API is free (key in `.env.example` as CENSUS_API_KEY — confirm it's set). **Google Sheets needs the Sheet ID + service-account credentials — still not provided; this blocks `output.py`.** Flag to user.
2. Department-relevance scoring for emails (press/IT/admissions are wrong-dept) — worth a light local-part-vs-topic heuristic in a later pass; the 15-sample is the seed corpus.
3. The 21 hard-WAF hosts: accept-and-flag is current behavior; revisit only if the client needs those specific orgs.

### What's next — Session 7

`population` (US Census API lookup per geo) then `output` (Google Sheets append + dedupe) — the last two Phase 1 components. Resolve Sheets credentials before `output.py`. After that, Phase 1 ships end-to-end rows.

---

## 2026-06-19 — Session 7: population + output + first full end-to-end run

### Security incident (caught at Step 0, handled)

`service-account.json` (a real GCP key) was found tracked — committed in `db9898d` (Session 6, swept in by an unscoped `git add -A`; `.gitignore` only had `credentials.json`) and pushed to `origin/main`. Per the user's instruction ("remove it from git so it's not exposed"), history was rewritten (`git filter-branch`) and force-pushed: `db9898d` and the key blob are gone from current history (local + remote `01335b6`), the file is now gitignored and untracked. **The key was NOT rotated** — and a force-push does not purge unreachable objects from GitHub immediately, so rotation in GCP (delete key `1f07f4d4…`, issue fresh) remains the only full fix. Recorded as memory + the sydashir-only commit/push rule in CLAUDE.md.

### Census keyless retired (blocker, worked around)

A pre-build check found keyless Census access was retired (~May 2026 — keyless calls 302→`missing_key.html`). The session's "keyless" premise is dead. `population/census.py` now takes a free `CENSUS_API_KEY` and degrades to `not_found` without one (population never blocks a row). `.env` has no key, so this run's Population column is uniformly blank — honest, not fabricated. A free instant key fills it in with zero code change. (ADR-008.)

### Done

- **`population/`** (`17db6e9`, `90cd40c`, `a2772f0`): models + `PopulationResult`; static 51-entry state→FIPS map; ACS5-2024 keyed client (`B01003_001E`), state→FIPS direct, county/city → cached per-state wildcard + offline `difflib` fuzzy match with name normalization (suffix/period/`st`↔`saint`), negative-sentinel rejection, no-key → not_found. 10 unit tests.
- **`output/`** (`2b6067f`, `dacec7e`, `8751428`, `4ed72ab`): brief-exact 11-column row schema (+ internal Confidence); `build_row` degrades every hole to blank; CSV writer with dedupe `(domain, geo)` + sort (geo→confidence→population desc); idempotent Google Sheets writer (read-then-append dedupe, sync client via `asyncio.to_thread`, typed `SheetsError` mapping 403/404/429, dynamic client contained behind `Any`). 16 unit tests. Pinned `google-api-python-client==2.197.0` + `google-auth==2.55.0`.
- **`pipeline.py` + `run` CLI** (`a5ecf4f`, `18ad959`): full chain discover→detect→extract→populate→assemble with per-geo isolation + funnel; `run --site … [--limit/--level] [--dry-run] [--out]` (CSV vs live Sheet).
- ADR-008 (`5a23158`); sydashir-only rule (`80bb1c6`). 207 unit tests green throughout.

### First full end-to-end run (5 cached geos, dry-run CSV)

Drove the real `run_pipeline` over the 5 validated geos (discovery from cache → **0 billed searches**), detect+extract live, populate (no key), CSV.

**Funnel:** 5 geos → 127 candidates → **69 detected** → **51 with-email / 57 with-phone** → **69 rows**. Population found: 0/69 (no Census key). Fetches: 298 (212 httpx + 43 Playwright). Billed searches: **0**.

Sample deliverable rows (Website | Specific Page | Email | Phone | Geo | Conf): floridahealth.gov | …/injury-prevention | health@flhealth.gov | (850) 245-4444 | Florida | high · oc.gov | bos4.oc.gov/mental-health-resources | fourth.district@ocgov.com | (714) 834-3440 | Orange County, CA | high · colorado.edu | …/counseling/ | — | (303) 492-1341 | Colorado | high · health.maryland.gov | …/bha/pages/help.aspx | — | (410) 767-6500 | Maryland | medium · ucdenver.edu | …/counseling-center | admissions@ucdenver.edu | (303) 315-5969 | Colorado | medium · newportbeachca.gov | …/departments | — | (949) 270-8150 | Newport Beach, CA | low.

**Deliverable verification (Playwright + provenance trace, no fabrication):** contacts are real — `fourth.district@ocgov.com` traced to `bos4.oc.gov/contact`, `admissions@ucdenver.edu` to `ucdenver.edu/about-cu-denver/contact-us`. The extractor cannot hallucinate (mailto/tel/regex over fetched same-domain HTML only). **Honest failure mode:** when a dept page and its own contact page lack an email, the fallback hops to the org's *generic* contact-us page and can surface a wrong-department inbox (ucdenver → admissions@). Real address, wrong department — the S6-flagged limitation, visible in medium-confidence rows. Provenance (which page a contact came from) is not yet a deliverable column — a transparency gap to consider.

### HELD (security)

The **live Google Sheets write was NOT performed** — it authenticates with the still-compromised, un-rotated key the user instructed not to reuse. Held until the key is rotated. CSV dry-run stands as the validated deliverable; the Sheets writer is unit-tested (header-ensure, append-only idempotency, error mapping) and ready to run post-rotation.

### Open questions / next steps

1. **Rotate the GCP key** (delete `1f07f4d4…`, fresh JSON) → then the live Sheet write + idempotency re-run can complete. **Add a free `CENSUS_API_KEY`** → population fills in.
2. Wrong-department fallback emails: tighten the contact-page ranker (prefer dept-topical contact pages; down-rank generic university/admissions inboxes), and consider surfacing `contact_page_url` as a deliverable column.
3. Phase 1 is feature-complete (components 1–2–4–5–7–8 + manual `run`). Phase 2 = Ahrefs authority-site discovery (component 3) + competitor link checker (component 6) + automated/scheduled triggers.

### Live close (2026-06-19, after key rotation)

Key rotated (`private_key_id` d97fe38c… ≠ compromised 1f07f4d4…); rotation gate passed → authenticated to Google. Ran the real `run_pipeline` over the same 5 cached geos → **live Google Sheet** (`1decvP…`):
- **69 rows landed, billed_searches = 0** (cache held; 298 fetches, 212 httpx / 43 playwright).
- **Idempotency:** immediate re-run appended **0** (skipped 69) — dedupe by Website+Geo Served holds.
- Population: 0/69 (no `CENSUS_API_KEY`; blank by design).
- Playwright (3 live rows): pages load, orgs match descriptions, contacts genuinely on-page (no fabrication). **New honest limitation:** body-text extraction can capture a THIRD-PARTY org's contact referenced on the page — `info@frsn.org` (+206 Seattle number) on a montgomerycountymd.gov page is a national crisis line, not the county's own contact. Distinct from the wrong-department issue; fix = constrain body-text emails/phones to the candidate's registrable domain (mailto/tel and contact-page hits are already safe). Confidence reflects page-detection quality, not contact attribution.

**Phase 1 MVP complete + live Sheet verified.** Phase 2 open: authority_filter (Ahrefs, unrestricted queries), link_checker (16 competitor domains), scheduled triggers; polish: domain-constrain body-text contacts + add a Contact Source column.

---

## 2026-06-23 — Session 8: contact attribution hardening (precision pass)

### Done (TDD throughout; sydashir; billed_searches=0)

Two Session-7 "real contact, wrong target" defects fixed, plus the page-confidence-vs-contact-trust split (ADR-009).

- **Domain-constrain body-text contacts** (`3622e42`): body-text-regex emails kept only when same registrable domain as the page (`EmailHit.same_domain` added); `mailto:`/contact-page hits exempt. RED→GREEN with the frsn.org regression fixture.
- **Contact provenance functions** (`443c961`): `contact_source_label()` + `contact_trust()` (pure, 12 tests).
- **Contact Source + Contact Trust columns** (`adb08d2`): added to OutputRow/CSV/Sheets (between Phone and Description → Geo Served now index 7); **Sheets schema migration** = clear+rewrite on header mismatch; steady-state stays append-only idempotent.
- **Cross-domain mailto fix** (`b403fd2`): the live frsn.org defect was a *mailto* to a third-party org (not body-text). Per the spec's banding (medium requires same-domain), a cross-domain mailto is now `low` + labelled "mailto (off-domain)" — flagged, not silently medium. (Can't be dropped without losing legit sibling-gov mailtos like `fourth.district@ocgov.com` on `oc.gov`.)
- **Sheets `replace` mode** (`bf0f942`): full clear+rewrite for value corrections (append-only can't update existing cells). Used to refresh the live sheet's corrected trust without re-fetching.
- 228 unit tests green; rotation gate re-confirmed (key `d97fe38c`, rotated) before any Google auth.

### Live validation (5 cached geos)

- **billed_searches = 0** (cache held; 296 fetches, 212 httpx / 40 playwright). Pipeline: 5 geos → 127 candidates → 68 detected → 50 email / 56 phone → 68 rows.
- **Migration:** WRITE1 cleared the old 11-col sheet + rewrote 68 (header_written). **Idempotency:** WRITE2 appended 0.
- **frsn.org (Montgomery County):** confirmed a cross-domain `mailto:` to a third-party crisis line. Now `Contact Source = "mailto (off-domain)"`, `Contact Trust = low` — verified by reading the row back from the live sheet. Not dropped (would lose legit sibling-gov contacts); flagged.
- **ucdenver admissions@:** `Contact Trust = low` (contact-page hop, generic local-part) — same-domain but wrong department, correctly caught by the trust band.
- **Contact-trust distribution (68 rows): high 1 / medium 27 / low 40** (the cross-domain-mailto fix moved 10 rows medium→low — appropriately conservative).
- **Playwright (6 rows):** pages load (dpscs transient 522 — gov flakiness); contacts confirmed real, same-domain enforced for body-text, off-domain flagged for mailto. No fabrication.

### Honest residuals

- **Wrong-org cross-domain mailto isn't *removed*, it's *flagged* low/off-domain.** We can't auto-distinguish a third-party mailto (frsn.org) from a legitimate sibling-gov mailto (ocgov.com on oc.gov), so precision-over-recall = flag, don't drop. Outreach reads the trust column.
- Body-text **phones** still can't be domain-checked (no domain) — a third-party phone mentioned on a page rides along, demoted below tel:.
- Page Confidence and Contact Trust are now distinct columns; a high-Confidence page can carry a low-Trust contact (that's the point).
- Append-only can't update existing rows' cells; value corrections need `replace=True` (one-time full refresh).

### Phase 2 (open)

`authority_filter` (Ahrefs DR, unrestricted query variants), `link_checker` (16 `COMPETITOR_DOMAINS`), scheduled triggers. Polish carried: domain-aware phone heuristics; surface contact provenance is now done.

## 2026-06-24 — Session 9: contact quality — diagnose, then lift (ADR-010)

Goal: raise *trustworthy* contacts after Session 8's honest 1/27/40, **without** relaxing the
trust bands. Diagnose-first; `billed_searches = 0` all session (cache held).

### Diagnosis first (`a15f703` — `docs: contact-quality diagnosis`)

- Built a throwaway diagnosis harness: re-ran discover→detect→extract over the 5 cached geos,
  faithfully replicated the *current* orchestrator best-pick (trust reproduced 1/28/39, within one
  row of the S8 baseline → faithful), and **probed** every site for a reachable same-domain
  department contact.
- Bucketed all 68 rows (brief's A–E): **A 2 / B 0 / C 10 / D 55 / OK 1 / E 0**. Two findings
  reshaped the plan: **B = 0** (the ranker was not mis-picking co-present emails) and the raw
  **D = 55 was inflated** by the narrow dept dictionary hiding real mailboxes.
- Honest ceiling quantified: **23 / 68 rows (34%) publish no same-domain email at all**
  (19 phone-only, 4 none). Written up in `docs/contact-quality-audit.md` with an evidence-derived
  signal set and a projection (high 6 / medium 16 / low 46).

### Fixes (TDD, RED→GREEN each)

- **`8994a4f` — department directory discovery.** Hop trigger fires unless a same-domain department
  inbox is already in hand (a generic `info@` no longer suppresses it); `find_contact_links` switched
  to single-best-match weighting and ranks staff/department-directory + MH-topic links above generic
  "contact us"; same-domain dept inbox ranks first. Shared `is_dept_localpart` added.
- **`3d14800` — rank contacts by department relevance.** Single evidence-derived `classify_localpart`
  (dept/role/generic/other) with an `environmental`/`developmental` guard (`environmentalhealth`
  contains `mentalhealth`); `_email_confidence` and the trust bands re-derived: off-domain→low,
  role/wrong-dept→low **even as same-domain mailto** (tightening), dept→high(mailto)/medium(hop),
  generic `info@`→medium (never high), phone-only→low. Removed the old narrow
  `_DEPT_LOCALPARTS`/`_ROLE_NOISE_LOCALPARTS`.
- **`31b48b0` — reject phone-glued email local-parts.** The first live re-run produced garbled emails
  (`303.458.3558counseling@…`, `724-8859smhservice@…`) the `\d{5,}` guard missed because separators
  break the run. Added a phone-shape guard; `regis` then yielded clean `counseling@regis.edu`.
- 262 unit tests green throughout; pyright strict 0 errors; ruff clean.

### Live validation (5 cached geos)

- **billed_searches = 0** (361 fetches, 261 httpx / 57 playwright). Rotation gate re-confirmed
  (key `d97fe38c`, rotated) before Google auth.
- `replace=True` rewrote **68 rows** (value-correction refresh for the new bands); idempotent append
  re-run added **0** at the 13-col layout.
- **Contact-trust distribution: high 1→6 / medium 27→18 / low 40→44.** high+medium 28→24 — it
  *drops*, because the old `medium` over-counted wrong-dept inboxes; quality rises (6× verified
  department mailboxes). Reported as a feature, not a regression.
- **10 promotions** (6 to high — all genuine dept mailboxes; headline: `montgomerycountymd.gov`
  off-domain `info@frsn.org` → same-domain `frs.peer_support_cism@…`; 4 to medium via directory hops:
  `sccollege counseling@`, `chhs behavioralhealthtaskforce@`, `regis counseling@`, plus `fsu`
  `vpsa-webmaster@` → `counseling@fsu.edu`). **11 demotions** (`admissions@`/`communications@`/
  `webmaster@`/`auditor@`/`mdmanual@`/`facultycouncil@`… medium→low; `info@csupueblo` high→medium).
- **Playwright-verified all 6 high rows** in a real browser (montgomery, howard, unco, fmu, pinellas,
  ivc): each is a same-domain `mailto:` on a department-relevant page. No fabrication.

### Honest verdict / residuals

- Quality materially better (high 1→6; the sheet no longer presents `admissions@`/`webmaster@` as
  trustworthy), but **~40% of authority pages publish no own-domain contact** — the real ceiling;
  phone + page URL is the deliverable there. The directory finder's measured lift is ~2 rows.
- Off-domain/role contacts are flagged `low`, not dropped (precision-over-recall). Body-text phones
  still can't be domain-checked. Population still blank (no `CENSUS_API_KEY`).

### Phase 2 (still open)

`authority_filter` (Ahrefs DR, unrestricted query variants), `link_checker` (16 `COMPETITOR_DOMAINS`),
scheduled triggers.

## 2026-06-24 — Session 10: link_checker (component 6) — competitor backlink detection (ADR-011)

Goal: fill the blank "Competitor Links" column — for each authority page, which of the 16
`COMPETITOR_DOMAINS` does it link OUT to? Precision over recall (a wrong flag misleads outreach
positioning). `billed_searches = 0` all session.

### Built (TDD, RED→GREEN each)

- **`2008e39` link checker models** — new `link_checker/` package (converted from the empty stub);
  `CompetitorLink` (domain/found_on/anchor/url) + `LinkCheckResult` (`competitor_domains` summary).
- **`d8b45e4` competitor link detection** — `check.find_competitor_links`: registrable-domain match
  (reuses `registrable_domain` + `COMPETITOR_DOMAINS`, the `is_competitor` primitives), `urljoin`
  resolution of relative/scheme-relative hrefs, own-domain skip, dedupe. 7 precision tests incl. the
  `rehabsomething.com` substring trap, protocol-relative, subdomain, clean-empty.
- **`6217274` resources-page discovery** — `resources.find_resources_link`: ONE same-domain
  resources/links/community-partners page (single-best-match weighting, junk/own-domain discipline).
- **`dad9cf9` link-check orchestrator** — `check_links_for_candidate`: detected page + ONE resources
  hop (mode b), ≤2 fetches, shared httpx→Playwright tier, per-candidate error isolation.
- **`952ad26` populate column** — wired into `pipeline.run_pipeline` (`_check_links` gathers per
  candidate, `return_exceptions=True`); `build_row` gains `competitor_links`; cell = `"; ".join(domains)`
  or `"—"`. "Competitor Links" was already a column (ADR-008) → value fill, no schema change.
- 282 unit tests green; pyright strict 0 errors; ruff clean.

### Live validation (5 cached geos)

- **billed_searches = 0**, 484 fetches (364 httpx / 75 playwright). Key rotation gate re-confirmed
  (`d97fe38c`).
- Wrote the run's rows to the live sheet via `replace=True` (value refresh) → 68 rewritten;
  idempotent append re-run added **0** (the populated column did not re-trigger appends — keyed on
  Website+Geo).
- **8 of 68 rows link to a competitor; 11 competitor links** — `samhsa.gov` ×8, `findtreatment.gov`
  ×1, `addictioncenter.com` ×1, `treatmentatlas.org` ×1.
- Examples: `cityoffrederickmd.gov` → SAMHSA + findtreatment.gov "treatment locator";
  `orangecoastcollege.edu` (Helpful Hotlines page) → treatmentatlas.org + samhsa.gov;
  `ndm.edu` (Counseling Center) → addictioncenter.com; `montgomerycountymd.gov` → SAMHSA national
  helpline; `umbc.edu`, `hcfl.gov`, `oc.gov`, `chhs.ca.gov` → SAMHSA.
- **Playwright-verified 4 flagged rows (0 false positives)** + 2 unflagged rows
  (howardcountymd.gov 0/1,416 anchors; unco.edu 0/105) — **no under-detection**.

### Honest recall limits

- JS-injected links on httpx-served pages (Playwright tier only on 403/SSL) are not seen.
- Deep pages beyond detected + one resources hop are not crawled (mode b tradeoff).
- `MAX_LINKS=500` parse cap: a page with >500 anchors (howard had 1,416) only exposes its first 500.
- Only ONE resources page is followed.

### Gotchas

- Scratch runner crashed twice before the good run: a missing `detect_for_geo` import, then an
  uncaught `httpx.ConnectTimeout` (the harness `gather` lacked `return_exceptions`; the production
  `_check_links` already has it → pipeline is robust). Fixed by reusing the pipeline's `_check_links`.

### Phase 2 (remaining)

- `authority_filter` (Ahrefs DR, unrestricted query variants) — **BLOCKED pending the user's Ahrefs
  API-access answer.**
- Scheduled/automated triggers on new geo pages; re-validation runs.

## 2026-06-25 — Session 11: scheduled auto-triggers + Docker (ADR-012) — MVP COMPLETE

Goal: run the pipeline on a schedule, processing ONLY newly-published geo pages (cost-safe — a
runaway job burning SerpAPI quota is the failure mode to design against), runnable identically on
the Mac and in a container. gh switched dev778d → sydashir at session start.

### Built (TDD, RED→GREEN each)

- **`ab92033` incremental run mode** — split detect from persist: `monitor.diff_sitemap` (fetch +
  parse + diff, no write); `run_monitor` = diff + save (unchanged behaviour). New `scheduler/`
  package: `run_incremental` detects new geos → injected `run_and_write` seam → persists state ONLY
  after success, ONLY for processed geos. Zero new ⇒ zero spend / zero writes / no state change; a
  crash never marks geos seen. `SitemapSource` Protocol for testability.
- **`4d560fe` scheduler entrypoint** — in-process APScheduler 3.x `AsyncIOScheduler` (4.0 is alpha);
  `run_tick` (per-site isolation) + `scheduled_tick` (real wiring) + `run_scheduler` (interval job,
  run-once-on-start, graceful SIGINT/SIGTERM). `schedule` CLI; `RUN_INTERVAL_HOURS`. (`8cec5df`
  chore: gitignore .playwright-mcp.)
- **`96582c7` safety rails** — `MAX_NEW_GEOS_PER_RUN` (default 25, cap+defer+warn);
  `MAX_BILLED_SEARCHES_PER_RUN` circuit breaker via `SerpApiClient(max_billed=…)` raising a distinct
  `QuotaExceededError` that `discover_many` re-raises (so it aborts the run, not swallowed as a
  per-query error) → `run_incremental` aborts without saving state. `.env.example` updated.
- **`b8c73ec` dockerfile** + **`b9f58d4` docker-compose** — single-stage py3.12-slim-bookworm + uv
  (pinned) + explicit chromium apt deps + `playwright install chromium` (venv binary, not `uv run`,
  which would build the not-yet-copied project — the build bug caught + fixed live); non-root;
  config-driven `--no-sandbox` (`playwright_no_sandbox`). Compose mounts secrets read-only (never
  baked) + bind-mounts `./data` (cache+state persist; no backlog re-processing). README run-on-Mac +
  run-via-Docker; `schedule --once` for single-tick/cron.
- 290 unit tests green; pyright strict 0 errors; ruff clean.

### Live validation (2026-06-25)

- **No-op tick** (host): both sites `new=0`, **billed=0, rows=0**, aborted=[] — quiet days cost nothing.
- **New-geo sim**: removed `…/orange-county/irvine/` from MHD state → one tick processed **exactly 1
  geo, billed=4** (that geo only, not the 23-geo set), **12 rows** appended to the live Sheet; AH
  `new=0`; state restored to 23. (Live Sheet now 80 rows.)
- **Docker**: image builds (3.56 GB); `docker compose run … schedule --once` runs a tick with
  structured logs; second container run (simulated restart) again `new=0` — **state persisted via the
  bind-mount, nothing re-processed**.
- **Caps**: unit-tested (cap+defer, max_billed→QuotaExceededError, discover_many re-raise, abort-no-save).
- **billed_searches this session: 4** (the single irvine geo). Rotation gate re-confirmed (`d97fe38c`).

### Full MVP status (all 8 brief components)

1. geo monitor (S3) · 2. discovery (S4) · 3. **authority_filter — intentionally SKIPPED per client
   (no Ahrefs API)** · 4. page detector (S5) · 5. contact extractor (S6, hardened S8–S9) ·
   6. population + output/Sheets (S7) · 7. link_checker (S10) · 8. scheduled triggers + Docker (S11).
**Phase 1 + Phase 2 COMPLETE** (component 3 deliberately out of scope, not missing).

### Operational follow-ups (not code)

Pick a cloud host (Docker-ready); add a free `CENSUS_API_KEY` to light up Population; show Jake.

## 2026-06-25 — Session 12: light up Population (Census key now present)

Goal: the Population component (built S7, ADR-008) returned blank for every row because there was no
Census key. The key is now in `.env` — verify the lookup works live, fill the column, verify accuracy
honestly. No new features. `billed_searches=0` (SerpAPI cached; Census is separate + free).

### Key

`CENSUS_API_KEY` was **absent** from `.env` (not an env-var name mismatch) — added the value the user
provided into the gitignored `.env`; now loads (len 40). Never echoed/committed.

### Step 1 — live lookup verified, one bug found + fixed (`c49ca75`)

Ran `CensusClient` live against ACS 5-year 2024 across all levels:
- Maryland (state) → `Maryland` = 6,206,011 (exact); Orange County, CA (county) → 3,165,820 (exact);
  Newport Beach, CA (city) → `Newport Beach city` = 83,845 (exact).
- **Bug:** the tricky `palos-verdes` (a peninsula/neighborhood, not a Census place) **fuzzy-matched the
  unrelated `Palo Verde CDP` (pop 75)** at ratio 0.909 — a confident wrong value. Fixed: tightened
  `_FUZZY_CUTOFF` 0.86 → 0.92 (TDD: added a decoy + neighborhood test). `palos-verdes` now honestly
  `not_found`. All 5 cached geos match **exact**, so the fix doesn't change the live fill. 291 tests.

### Step 2 — column filled live (`billed_searches=0`)

Enriched the 68 S10 rows with per-geo population (Census-only, no SerpAPI) and `replace`-wrote:
- All 5 cached geos resolve exact: **Maryland 6,206,011 · Colorado 5,862,189 · Florida 22,416,077 ·
  Orange County, CA 3,165,820 · Newport Beach, CA 83,845.**
- **68/68 rows filled, 0 not_found** (the 5 cached geos are all clean state/county/city; the only
  not_found-class case — neighborhoods like palos-verdes — isn't among them).
- `WRITE1_REPLACE` rewrote 68; `WRITE2_IDEMPOTENCY` appended 0. Rotation gate `d97fe38c` re-confirmed.
- Note: the `replace` reset the sheet to the canonical 68 rows; the 12 `irvine` rows from the S11
  new-geo *simulation* were dropped (a test artifact; re-addable, cached → billed=0).

### Step 3 — accuracy spot-check (4 rows, web-verified, cross-state lens)

All four are an **exact match to the published ACS 2024 5-year figure** and the **right geography**
(no Springfield-style cross-state confusion):
- Maryland 6,206,011 ✓ (only same-named alt is a tiny NY town, off by 3 orders).
- Florida 22,416,077 ✓ (Vintage-2024 point-in-time is 23.4M — different product, ~4%, expected).
- Orange County **CA** 3,165,820 ✓ (FIPS 06059; OC-FL ~1.45M / OC-NY ~0.4M ruled out — the state-FIPS
  scoping disambiguates correctly).
- Newport Beach **CA** 83,845 ✓ (geoid 16000US0651182, 06=CA, not 44=RI Newport).

### Status

Deliverable now has **Population filled and accuracy-verified**. MVP complete + every brief column now
populated (except competitor-free rows showing `—`, and component 3 Ahrefs intentionally skipped).
No new ADR (the fuzzy-cutoff change is a parameter tightening within ADR-008, not a design change).

## 2026-06-26 — Session 13: database foundation (Postgres) — SaaS build begins (ADR-013)

The repo becomes a single-customer SaaS. **Phase A:** add a Postgres source-of-truth UNDER the proven
pipeline without breaking anything. The Sheet stays an export. gh switched dev778d → sydashir.

### Built (TDD where it earns it; real-Postgres tests, not mocks)

- **`7474911` postgres service** — `postgres:16` in docker-compose (host **5433**, since a separate
  project owns 5432), named volume, env-driven; `DATABASE_URL` in `.env.example`. No baked creds.
- **`7f46434` schema + migrations** — SQLAlchemy 2.x async models (`prospects`/`runs`/`geos`) from
  OutputRow; native PG enums (`trust_band`, `source_tag`, `run_status`, `geo_level`); the
  `(website, geo_served)` dedup key is now a real `UNIQUE` constraint. **psycopg 3** (one driver for
  async app + sync Alembic). Alembic initialised, initial migration autogenerated + applied. Deps
  pinned (sqlalchemy 2.0.51 / alembic 1.18.5 / psycopg[binary] 3.3.4).
- **`42ee1ee` repository layer** — async repository pattern (`upsert_prospect`, `get_prospects` with
  trust/source/geo/level filters, `create_run`/`finish_run`, `upsert_geo`, `get_geos`); 5 tests
  against a **real Postgres** via testcontainers (skip cleanly if Docker absent).
- **`ed72c5f` pipeline → DB** — `db/ingest.persist_pipeline_run` bridges OutputRow → ProspectIn
  (repository stays pipeline-agnostic); opt-in **`run --persist-db`** writes the Sheet/CSV AND the DB.
  `run`/`schedule` with no new flag are byte-identical to before. 1 ingest test.
- **`a9af0eb` ADR-013** (this design).
- 297 tests green (291 existing + 6 DB); pyright strict 0 errors; ruff clean. The pipeline + CLI are
  unbroken (the `--persist-db` block is gated, default off, so the old path is unchanged).

### DB proof (Step 5, 2026-06-26 — pipeline over the 5 cached geos, `billed_searches=0`)

1. **68 prospect rows** in Postgres; a 2nd persist of the same rows left it at **68 (not 136)** — the
   unique constraint held → DB-level idempotency.
2. **`runs` row recorded**: site=both, status=success, rows_written=68, billed_searches=0,
   geos_processed=5, finished_at set. (2 runs recorded across the two persists.)
3. **`geos` populated** (5): ah/colorado, ah/maryland, mhd/florida, mhd/orange-county (county),
   mhd/newport-beach (city).
4. 5 sample prospects queried straight from Postgres render every column (website, geo, email,
   contact_trust enum, population, confidence, competitor_links).
5. **`contact_trust='high'` filter → exactly 6 rows** (unco.edu, fmu.edu, pinellas.gov,
   howardcountymd.gov, montgomerycountymd.gov, ivc.edu) — proving the UI's filtering will work.

Nothing broke: full suite 297 green; `write_csv` (the `run --dry-run` output path) still writes the
68-row, 13-col CSV. CLI loads with `--persist-db` exposed.

### Monorepo layout (ADR-013)

`src/authority_finder/` stays the core library; persistence is the subpackage `src/authority_finder/db/`
(models/session/repository/ingest); Alembic at repo root. `backend/` (FastAPI, Phase B) + `frontend/`
(React, Phase C) reserved as top-level siblings.

### What Phase B (backend API) builds on this

A FastAPI app that imports `authority_finder.db.repository` to serve `GET /prospects` (with the
trust/source/geo/level filters already implemented) + run history from `runs`, behind auth — reading
the Postgres source-of-truth this phase established.

---

## 2026-06-30 — Session 14: Phase B — backend API (FastAPI)

### Done

SaaS build, Phase B (ADR-014). Built the FastAPI backend over the Phase A repository + pipeline. Standalone, verified by HTTP + tests; the pipeline and the Google Sheet write are untouched. Same layer-by-layer + TDD discipline. Research workflow (context7) confirmed current FastAPI/uvicorn/pydantic-v2 shapes first.

- `acf5fa2` **feat: add repository read functions for api** — `get_prospects` gains `limit/offset`; new `count_prospects`, `get_prospect`, `get_runs`, `get_run`, `count_runs`. (Later `9eb0776` re-typed the shared filter helper — see below.)
- `8873d9c` **refactor: extract persist_prospects from persist_pipeline_run** — a core that writes geos+prospects under an *existing* run_id, so the API's background task can persist under the run row it opened/finishes itself.
- `335cc16` **feat: add fastapi backend skeleton** — `backend/` package: app factory + lifespan (async engine/sessionmaker on `app.state`, disposed on shutdown), request-scoped `get_session`, env-driven CORS, `GET /health` (DB-connectivity probe). Testcontainer fixtures moved to a top-level `tests/conftest.py` (shared by db + api tests). `src/authority_finder/py.typed` marks the package typed for the backend's strict checks. `cors_allow_origins` setting added. fastapi 0.138.2 + uvicorn[standard] 0.49.0 pinned; `backend` wired into ruff/pyright/pytest.
- `e4515e6` **feat: add prospects api endpoints** — `GET /prospects` (trust/source/geo/level filters + limit/offset paging + total count) + `GET /prospects/{id}` (404 on miss). Pydantic `from_attributes` models (`ProspectOut`, generic `PageOf[T]`) expose only scalar FKs so serialization never lazy-loads.
- `6971e77` **feat: add runs api endpoints** — `GET /runs` (history, newest first, paged) + `GET /runs/{id}` (the status the UI polls).
- `2b15e72` **feat: add run trigger with background execution** — `POST /runs` opens a run (running), returns the id at **202**, runs the pipeline in a FastAPI BackgroundTask that opens its **own** session (the request session is closed by then), writes **BOTH** Postgres and the Sheet, and finalizes the row to success/failed. Reuses the S11 cost-safe `run_incremental` (no-new-geos → 0 spend) + the `max_new_geos`/`max_billed` caps; `full` mode re-runs all known geos (circuit-broken). Startup orphan-sweep flips stuck `running` rows to `failed`.
- `b9eae6c` **test: backend api cors and docs coverage** — CORS (configured origin echoed + credentials, preflight) + Swagger `/docs` served.
- `9eb0776` **fix: type prospect filter without typevartuple** — pyright 1.1.409 rejects `Select[*Ts]`; share the typed WHERE conditions (`list[ColumnElement[bool]]`) instead. (A single-file pyright check earlier masked this; whole-project caught it.)

318 tests green (291 existing + 27 db/api: 8 repository, 2 ingest, 17 api). pyright strict 0 errors (4 pre-existing `reportMissingTypeStubs` warnings on untyped libs). ruff + format clean.

### Live validation (2026-06-30, dev Postgres on :5433, 68 prospects / runs / 5 geos from S13)

- App boots under uvicorn; `/health` → `{"status":"ok","database":"ok"}` (200); OpenAPI 3.1 + `/docs` generate; paths: `/health`, `/prospects`, `/prospects/{id}`, `/runs`, `/runs/{id}`.
- `GET /prospects` → total **68**; `?contact_trust=high` → **6** (unco/fmu/pinellas/howard/montgomery/ivc); `?source_tag=AH` → 23; pagination (limit 5, offset 0 vs 5) pages distinctly, total stays 68; `/prospects/{id}` renders every column; missing → 404.
- `GET /runs` → 2 runs newest-first (both success/68/billed=0/5 geos); `/runs/{id}` detail; missing → 404.
- `POST /runs {site:both, mode:incremental}` → **202 + run_id=3, running** immediately; polling `GET /runs/3` showed `running` for ~10s then **`success`**; **billed_searches=0**, 0 rows, prospects **68→68** (Sheet/DB untouched). Free sitemap diff confirmed **0 new geos** for both sites first, guaranteeing the no-op. Run history 2→3.

### Decisions / why

- **Background runs via the runs table (202 + poll), FastAPI BackgroundTasks** over fire-and-forget / Celery; the task opens its own session; success/failure finalized in separate clean sessions; startup orphan-sweep. (ADR-014.)
- **API runs reuse the S11 cost rails** — an endpoint that can spend SerpAPI must honor `max_billed` + `max_new_geos`.
- **Sheet stays a permanent output**; the DB write is additive (under the run_id).
- **Endpoints unauthenticated this phase** — auth is Phase D (documented, not omitted).

### Gotchas

- Whole-project pyright catches what a single-file check can miss — `Select[*Ts]` (PEP 695 TypeVarTuple) passed my `pyright <file>` (mis-grepped) but failed `pyright .`. Always run the project-wide strict check before committing.
- ASGITransport does NOT run the lifespan, so tests set `app.state.sessionmaker` (or override the deps) themselves; it DOES await BackgroundTasks, so a triggered run is already finalized when `client.post` returns — deterministic lifecycle tests.
- testcontainers can transiently `ConnectionError` on container start under load (full-suite first run); a re-run is clean — not a code issue.
- The `run --dry-run` verification discovered an **uncached** geo and so spent **4 billed searches** (the `run` CLI bills for uncached geos even in dry-run). Minor unintended spend; target a cached geo next time.
- Docker daemon was down at session start (new day) — started it; dev Postgres came back healthy on :5433 with the S13 data intact (named volume).

### What's next (Phase C — React UI)

Consumes these endpoints: prospects table ← `GET /prospects` (the trust/source/geo/level filters + paging), run history ← `GET /runs`, trigger ← `POST /runs` then poll `GET /runs/{id}`. Then Phase D: auth over all of it. Run the API: `uv run uvicorn backend.app:app` (reads the same `.env`).

---

## 2026-06-30 — Session 15: Phase C1 — the Prospects dashboard (first real UI)

### Done

SaaS build, Phase C1 (ADR-015). The first real product screen: a dense, professional Prospects table the outreach team works in, reading LIVE data from the Phase B API over real Postgres. Pipeline / DB / API / Sheet write all untouched — the UI is purely additive and talks ONLY to the API. context7 confirmed the current frontend stack shapes (Tailwind v4 CSS-first, TanStack Query v5) before building.

- `634d63c` **feat: scaffold react frontend** — Vite + React 19 + TS + Tailwind v4 + TanStack Query under `frontend/`. Typed API client (`src/api/`) mirroring the backend models (`Prospect`/`PageOf<T>`/`Run`, the trust/source/level unions); env-driven `VITE_API_URL`. App shell with a live `/health` "Backend connected" indicator. Two-process dev flow (uvicorn :8000 + vite :5173, in the CORS allow-list).
- `25ab2af` **feat: add prospects table** — dense table over `GET /prospects`: Website (frozen first column), Specific Page (link), Email, Phone, Contact Trust (colored badge), Geo Served, Source (MHD/AH badge), Competitors (flagged count), Population (right-aligned tabular), Confidence. Sticky header, hover highlight, graceful horizontal scroll; loading skeleton / error / empty states.
- `cb37913` **feat: add prospects filters and pagination** — filter bar wired to the API query params (Contact Trust / Source / Level) with active-state highlight + reset; live updates via TanStack Query (`keepPreviousData`, dim-while-fetching). Pagination footer (`limit`/`offset`, `total`) with "Showing X–Y of N".
- `b320425` **feat: add prospect detail view** — right slide-over drawer on row click: full prospect in labelled sections (trust/confidence/source, contact email+phone links + Contact Source provenance, specific-page link, organization, geo + population, competitor links listed, record meta). Backdrop + Escape to close; content retained through the slide-out.

Stack pinned: vite 8.1, react 19.2, typescript ~6.0, tailwindcss 4.3 + @tailwindcss/vite, @tanstack/react-query 5.10.

### Live validation (2026-06-30, Playwright against the running stack — dev Postgres :5433, 68 prospects)

- Shell connects: `/health` → **"Backend connected"** (green).
- Table renders the **68** real rows from Postgres via the API (real domains/emails — NOT mocked); footer "Showing 1–50 of 68".
- **Trust=high → exactly 6** ("Showing 1–6 of 6": unco/fmu/pinellas/howard/montgomery/ivc); **Source=AH → 23**. Pagination Next → "Showing 51–68 of 68". Active-filter highlight + Reset work.
- Row click → drawer with full real data: Montgomery County incl. Contact Source provenance + the competitor link **samhsa.gov** listed; email/phone/page links clickable.
- **Graceful failure:** stopped the backend → header flips to "Backend offline" (red), an error card "Couldn’t load prospects" + Retry, footer "0–0 of 0" — NOT a white screen. Restarted → reconnects.

### Nothing broke

Backend suite **318 passed**, pyright strict 0 errors, ruff clean (no Python changes this session). Frontend: `tsc -b` clean, `vite build` succeeds, oxlint clean. Backend API / CLI / Sheet write unchanged.

### Decisions / why (ADR-015)

- **TanStack Query for server state** (caching/dedup/keepPreviousData) over hand-rolled fetch+useEffect.
- **Typed API client is the only seam** — UI never touches DB/pipeline; the contract is compile-time-enforced.
- **`VITE_API_URL` + the Phase B CORS** (no dev-proxy) — fewer moving parts; revisit for Phase D auth cookies.
- **Dense internal-tool aesthetic** — zinc/indigo, 13px tabular, frozen column, colored trust/source badges, slide-over drawer (keeps table context).

### Gotchas

- The TS 6 scaffold enables `erasableSyntaxOnly` → TS parameter-property shorthand (`constructor(readonly x)`) is disallowed; declare fields explicitly.
- The scaffold uses **oxlint** (not eslint) and ships current versions (Vite 8 / TS 6 / React 19) — ahead of older muscle memory; trust context7 + the scaffold.
- Tailwind v4 is CSS-first: `@import "tailwindcss"` + `@tailwindcss/vite` plugin + `@theme`; do NOT add a `tailwind.config.js`/PostCSS (v3 muscle memory).
- Vite binds `localhost` (IPv6 `::1`); `curl 127.0.0.1:5173` can read as down while the browser is fine — verify the UI with Playwright, not curl.

### What's next (Phase C2)

Run-history view (`GET /runs`) + a "Run now" button (`POST /runs`, site/mode) + run-status polling (`GET /runs/{id}` → running → done, surfacing billed/rows/geos). Then Phase D: auth over the whole stack.
Run the UI: `docker compose up -d postgres` + `uv run uvicorn backend.app:app` + `cd frontend && npm run dev`.

---

## 2026-06-30 — Session 16: Phase C1-Redesign — product identity + dashboard + export

### Done

SaaS build, Phase C1-Redesign (ADR-016). A deliberate visual + UX overhaul to make the dashboard feel like a real SaaS product (identity, hierarchy, craft), plus the EXPORT the user asked for. Data already correct; this upgrades PRESENTATION and adds export. Pipeline/DB/API auto-write untouched; UI talks only to the API. (frontend-design skill file absent on this machine — the art direction in the prompt was the spec.)

- `332ec5a` **feat: add stats endpoint** — `GET /stats` (one FILTER-aggregate query + latest run) for the dashboard cards; `repository.get_prospect_stats`; tested vs real Postgres.
- `5aa6c60` **feat: export to a new sheet tab** — a plain service account can't create standalone spreadsheets (Drive 403), so `POST /export/sheet` adds a uniquely-named NEW TAB to a workbook it can edit (`EXPORT_SHEET_ID`, default the master) and returns its `#gid` URL — the auto-write tab (`Sheet1`) is never touched. `SheetExporter` (addSheet + values), `prospect_to_output_row`, mocked-Google tests.
- `99a2311` **feat: add design system and app shell** — AuthorityScout identity (radar logomark), dark-first CSS-variable token system (teal brand, semantic tokens via Tailwind v4 `@theme inline` + `@custom-variant dark`), theme toggle persisted (no-flash init), app shell (sidebar + topbar). Existing components re-themed to tokens. lucide-react icons.
- `d3c94d3` **feat: add dashboard overview cards** — five crafted cards from `GET /stats`.
- `acd51e8` **feat: redesign prospects table** — client-side sort (ranked trust/confidence, numeric population, competitor count) + a Columns visibility menu (Website frozen); polished badges + states.
- `432ab3d` **feat: add export actions** — topbar Export CSV (client-side, pages all matching rows) + Export Sheet (toast with a link); Toast, `apiPost` + `getAllProspects`.
- `6ff66b0` **feat: redesign prospect detail drawer** — actionable: trust rationale, copy-to-clipboard + mailto/tel, prominent resource link, competitor chips.

Pinned: lucide-react ^1.22. New backend setting `EXPORT_SHEET_ID`.

### Live validation (2026-06-30, Playwright against the running stack)

- **Identity / dark theme:** reads as a designed product (radar logo + AuthorityScout, sidebar nav, teal brand, dark surfaces). Light toggle coherent + persisted.
- **Stat cards (real):** Total **68** (across 5 geos), High-Trust **6** (9%), With Email **74%** (50/68), Geos **5**, Last Run success.
- **Table:** 68 real rows; sort Population asc → Newport Beach (83,845) first; Columns menu hides Phone; **Trust=high → 6** (filters intact).
- **Export CSV:** downloaded all **68** rows with the deliverable columns (verified header + 68 data rows).
- **Export Sheet (live, rotation gate passed — key `d97fe38c…`):** curl + UI each created a new tab with the filtered rows and returned a `#gid` URL; master **Sheet1 stayed 69 rows — untouched**; the 2 proof tabs were deleted afterward, leaving the master pristine (just `Sheet1`).
- **Drawer:** actionable — trust rationale ("a department/role inbox on its own domain — safe to reach out"), email/phone copy + mailto/tel buttons, resource link + org description, samhsa.gov competitor chip, details.

### Nothing broke

Backend suite **324 passed** (318 + 6 stats/export), pyright strict 0, ruff + format clean. Frontend tsc clean, vite build succeeds, oxlint clean. API additive only (`/stats`, `/export/sheet`); the `run`/`schedule` CLI and the master Sheet auto-write are unchanged.

### Decisions / why (ADR-016)

- **Export = new tab, not new spreadsheet** — a plain SA can't create standalone sheets (403); a new tab in an editable workbook works + leaves Sheet1 untouched. `EXPORT_SHEET_ID` for a dedicated export workbook.
- **Dark-first token system** (teal brand) so both themes are coherent and everything themes through CSS variables.
- **`GET /stats` endpoint** over client-side derivation — cleaner, scales, tested.

### Gotchas

- Service accounts have NO Drive storage → `spreadsheets.create` 403s. Use a new tab (`addSheet`) in a workbook the SA can already edit.
- The `/prospects` `limit` caps at 200 — the CSV export must page through (a `limit=10000` call 422s).
- A long-lived backend started before new routes were added serves the OLD app (no `--reload`) — restart uvicorn after adding endpoints (`/stats` 404'd until restart).
- Vite picks the next free port if 5173 is held by a leftover dev server → the new origin isn't in CORS. Kill stale vite first; one server per background command.

### What's next (Phase C2)

Wire the Runs nav item into this shell: run history (`GET /runs`) + a "Run now" trigger (`POST /runs`, site/mode) + status polling (`GET /runs/{id}` → running → done). Then Phase D: auth over the stack. Set `EXPORT_SHEET_ID` to a dedicated export workbook for production.

---

## 2026-07-01 — Session 17: Phase C2 — Runs screen + "Run now" + live status

### Done

SaaS build, Phase C2 (ADR-017) — the last UI screen. Built the frontend Runs view + a "Run now" trigger + live status polling into the "Runs" nav slot the C1-redesign shell reserved. Backend (GET/POST /runs from Phase B) untouched; engine/DB/API/Sheet/dashboard unchanged; UI talks only to the API. **With this the UI is complete** (prospects + runs + trigger). context7 confirmed the TanStack Query v5 polling idiom.

- `6a0ad3c` **feat: add runs api, trigger, and status badge** — client `getRuns` + `triggerRun`; `useRuns` (polls every 2s while any run is running, stops when terminal) + `useTriggerRun` mutation; `RunStatusBadge` (spinner while running); `timeAgo`/`duration` helpers; the Run now control (site + cost-safe/full mode picker, full-run credit warning).
- `fafd22f` **feat: add runs history view** — activated the Runs nav (view switching in the shell; extracted `ProspectsScreen` from App); `RunsScreen` lists `GET /runs` (site/status/relative-times/geos/rows/billed/notes) with the dashboard's table craft + loading/empty/error states; live-updates via polling; on a run turning terminal it invalidates prospects + stats so the dashboard refreshes. Topbar search made optional.

### Live validation (2026-07-01, Playwright against the running stack)

- **Runs list:** rendered the 3 real runs from Postgres (S14 no-op + two S13 runs) with correct details — themed coherently in **dark and light**.
- **Run now:** popover surfaces the cost-safety (New geos only = default, "Cost-safe"; Full re-scan = "may use search credits"). Both/incremental → "Run started" toast + a new run row.
- **Cost-safe no-op:** 0 new geos (confirmed by a free sitemap diff first), so each triggered run completed **billed=0, rows=0, geos=0** — shown correctly in the UI (Billed —, Rows 0). No quota spent.
- **Live polling:** the new run appeared and flipped running → **success without a manual refresh**; the total incremented 3 → 6 across triggers, each resolving live.
- **Post-run refresh:** the Prospects **Last Run** card updated to "Jul 1, 2026" after the run (stats invalidation fired); Total stayed 68 (no-ops add nothing).
- Design: the Runs screen matches the dashboard's product quality (same shell, table, badges, theming). (The no-op finishes in ~5s — faster than a screenshot round-trip — so the transient running spinner wasn't freeze-framed; the live count increment + auto-resolution prove the polling.)

### Nothing broke

Backend suite **324 passed** (no backend changes this session), pyright strict 0, ruff clean. Frontend tsc clean, vite build succeeds, oxlint clean. API / CLI / master Sheet auto-write unchanged.

### Decisions / why (ADR-017)

- **View switching in the shell (no router)** — two screens + a soon-tab; App is the single composition point Phase D slots into.
- **Poll the list via `refetchInterval`-as-a-function** — self-stopping when all runs terminal; simpler than per-run polling.
- **Surface the cost-safety in the UI** — cost-safe default + full-run credit warning; caps enforced backend-side.
- **Cache invalidation on run completion** — prospects + stats refresh automatically.

### Gotchas

- The no-op run completes in ~5s — faster than a Playwright screenshot round-trip — so freeze-framing the running spinner is impractical; verify polling by the live count increment + auto-resolution instead.
- Stale vite from a prior session holds :5173 → new vite drifts to :5174 (off the CORS list). Kill stale vite first.
- A backend started before new routes (no `--reload`) serves the old app — but this session added no backend routes, so the S16 backend served fine.

### What's next — UI COMPLETE

Prospects + Runs + trigger are all shipped. Remaining: **Phase D** (auth over the stack — the shell reserves user-menu/Settings slots) and **Phase E** (hosting/deploy). Run the stack: `docker compose up -d postgres` + `uv run uvicorn backend.app:app` + `cd frontend && npm run dev`.

---

## 2026-07-03 — Session 18: Phase D — authentication (Google sign-in + allowlist)

### Done

SaaS build, Phase D (ADR-018) — makes the app private. **Note:** the phase was requested as "resume from Step 6", but the auth implementation did NOT exist in the repo (no auth router/config/login) — so this session built Phase D from scratch (Steps 1–5) then verified (6–9). The pipeline/CLI/scheduler (headless, no API auth) stay untouched. Research workflow (context7) confirmed the current google-auth / @react-oauth/google / PyJWT-cookie / pydantic-settings shapes first.

- `1dd317e` **feat: add auth config and token/session core** — Settings: `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `ALLOWED_EMAILS` (CSV→list validator via NoDecode), `JWT_SECRET`, session hours + cookie-secure. `backend/auth.py`: server-side Google verify (`google-auth`, aud+issuer+`email_verified`, `ValueError|GoogleAuthError`→401), allowlist, HS256 session mint/decode, `get_current_user` (cookie/Bearer→401). PyJWT 2.13.
- `b0e59f5` **feat: add auth routes and guard data routers** — `POST /auth/google` (verify→allowlist 403→JWT→httpOnly SameSite=Lax cookie→user), `GET /auth/me` (401), `POST /auth/logout`. Verifier is a dependency (tests inject a fake). Data routers guarded; health + `/auth/google` public. 14 auth tests; existing api fixtures bypass auth with a test user.
- `7416b62` **feat: add auth api client and login screen** — typed auth client (`credentials:'include'`), `useMe` hook, on-brand Login (logo + `@react-oauth/google`, 403 not-authorized state).
- `68576a0` **feat: gate app on sign-in with user menu and logout** — App gates on `useMe`; GoogleOAuthProvider + a global 401 handler; sidebar user menu (avatar/name/email) + logout.
- `390a830` **fix: auth gate loop and logout** — two bugs caught live: the global 401 handler looped on `/auth/me`'s own 401 (scope to non-`me`); the gate kept showing the app after logout (TanStack retains data on error → also gate on `isError`).

### Live validation (2026-07-03) — noting live-browser vs backend-verified

- **Live browser:** unauthenticated → on-brand login screen (logo + "Sign in with Google", "access is limited to authorized team members"). With a valid session → the dashboard loads; sidebar shows the signed-in user (Intake Team / integrations@districtbehavioralhealth.com / avatar); features work (Trust=high→**6**, Source=AH→**23**, runs 6); **logout → cookie cleared + back to login**.
- **Backend (curl + tests):** `/prospects`,`/stats`,`/runs`,`/auth/me` → **401** unauthenticated; bad Google token → **401**; validly-verified-but-not-allowlisted email → **403** (test, mocked verified token); minted session → `/auth/me` 200 + `/prospects` 200.
- **NOT live-browser:** the real Google popup can't complete headless — the logged-in state was verified by injecting a real backend-minted session (a legitimate app session standing in for a completed login); Google *verification* is covered by the backend tests, not fabricated.
- `.env` confirmed **NOT** tracked (git ls-files empty) and never committed; the OAuth client id is public (also the frontend var).

### Nothing broke

Backend suite **338 passed** (324 + 14 auth), pyright strict 0, ruff clean. **CLI (`run`/`schedule`) + scheduler load and are unaffected** (auth lives only in `backend/`; they never hit the API). Master Sheet auto-write unchanged. Frontend tsc clean, vite build succeeds, oxlint clean.

### Decisions / why (ADR-018)

- **Google sign-in verified server-side + email allowlist** — no passwords, no user-admin UI for a single org; access is a config value.
- **App's own JWT in an httpOnly SameSite=Lax cookie** (not Google's token) — XSS-safe, decoupled; Lax works because localhost:5173↔8000 is same-site.
- **Guard the data routers, keep /health + /auth/google public.**

### Gotchas

- pydantic-settings JSON-decodes list env vars — a CSV `ALLOWED_EMAILS` needs `Annotated[list[str], NoDecode]` + a splitting validator.
- A global "401 → re-check auth" must EXCLUDE the auth-check query itself, or its 401 loops forever.
- TanStack Query retains the last `data` on a refetch error — the logout gate must check `isError`, not just `!data`.
- Cookies are host-scoped (ignore port), so a `localhost` cookie set on :5173 reaches the API on :8000 — that's why SameSite=Lax + same-site works cross-port.
- The Google button is a GSI iframe (can't be CSS-styled); brand around it. Its origin must be in the OAuth client's Authorized JavaScript origins.

### What's next — Phase E (hosting)

Deploy the stack; add the production URL to the OAuth client's Authorized JavaScript origins; set env on the host (`ALLOWED_EMAILS`, `JWT_SECRET`, OAuth creds, `AUTH_COOKIE_SECURE=true`, prod `CORS_ALLOW_ORIGINS` / `VITE_API_URL`). Add each teammate (and `meetashirr@gmail.com` if it should sign in) to `ALLOWED_EMAILS` + as OAuth test users.

## 2026-07-06 — Session 19: Phase F1 — scale-test the pipeline at real volume (cost-capped)

First run of the pipeline over **unseen** geos at real volume, hard-capped at **40 billed SerpAPI
searches**. Goal: find what breaks beyond the 5 cached geos, fix the real defects, and give an honest
production-readiness verdict + full-run cost — without spending the shared budget.

### What was done

- **Free recon (no spend):** both live sitemaps → **72 live geo pages** (MHD 23: 2 state/4 county/17 city;
  AH 49: all state), 8 already cached, **64 new**; projected full-run ≈ **253 billed** (~$3.80). AH is
  state-only — county/city depth is MHD-only.
- **Capped 8-geo sample** (3 AH state incl. rural Wyoming, 2 MHD county, 3 MHD city incl. the Palos Verdes
  fuzzy-match trap), projected 30 billed, `max_billed=38` backstop. **First run: 29 billed**, 8 geos →
  167 candidates → 87 rows; no crashes, no whole-geo failures, DB idempotent (run #7, 87 prospects),
  population 74/87 exact. **Session billed total: 30 of 40.**
- **Adversarial analysis (multi-agent) → 6 confirmed precision defects**, each fixed via TDD, atomic commit:
  `e4caf0c` reject interior-whitespace emails (HIGH — an undeliverable spaced address was published at HIGH
  trust, out-ranking the valid inbox); `ff4b56f` reject glued-label junk emails; `c46edf7` exclude national
  federal portals (govinfo.gov/data.gov) as candidates; `2fb5fc8` wrap transport errors so the crawl
  fallback runs; `29ede7f` scope the crawl to the per-agency dedupe key (dol.ny.gov no longer hops into
  omh.ny.gov); `c29ec44` treat an empty SerpAPI result as valid (not a hard error → no miscount, now cached).
- **Cached re-run verified every fix on real data** (billed 1 — one previously-uncached Wyoming query that
  now returns results): 0 federal-portal rows; pba.edu → `counseling_wellness@pba.edu`; oc.gov →
  `carecoordination@ceo.oc.gov`; dol.ny.gov → `dol.ny.gov/about-us`; Wyoming errors=0; **0 junk emails**.
  Corrected: 83 rows, 44 email (53%), 73 phone (88%), population 70/83 (84%).
- **344 tests** (338 + 6), pyright 0, ruff clean; CLI + scheduler load; master Sheet untouched; dev DB
  restored to canonical 68/6/5 (the pre-fix scale rows were throwaway test data).

### Decisions / why (ADR-019)

- **Report the free live-geo count before spending** — cost transparency; the cache makes the 5 old geos free.
- **Controlled sample script, not the bare `run` CLI** (which loads all geos) + a hard `max_billed` backstop.
- **Fix only adversarially-confirmed defects** — the 403/DNS/robots failures are expected external noise
  (~23% of candidates), per-candidate isolated, not bugs.
- **Deferred the ~9% wrong-state risk** (scorer's wrong-state reject is text-only, no domain geolocation) —
  unconfirmed + a bigger change; flagged as the top scale risk for a spot-check before the full run.

### Verdict

Infrastructure **scales safely** (cost-bounded, idempotent, honest, per-geo isolated). With the 6 fixes,
the pipeline is ready for a full **64-geo run ≈ 253 billed (~$3.80)**, subject to the wrong-state spot-check.

### Gotchas

- The local `.env` had `SERPAPI_KEY` but the code expects `SERPAPI_API_KEY` (per `.env.example`) — the key
  silently loaded as empty (zero results, no error). Renamed the local var; not a code change.
- SerpAPI signals a genuinely-empty result with HTTP 200 + an `error` string ("hasn't returned any results")
  — distinct from real errors; must be treated as empty, not raised.
- State `.gov` portals share one registrable domain (`ny.gov`) — use the per-agency `dedupe_key` for the
  crawl guard or agencies bleed into each other.
- testcontainers DB tests error transiently right after Docker starts (port/resource contention) — pass
  when Docker is warm; re-run the suite.

## 2026-07-06 — Session 20: Phase F2 — wrong-state validation

Hardening. Session 19 flagged ~9% wrong-state / out-of-geo candidates as the top quality risk for the full
64-geo run (concentrated on the 24 state-level AH geos). The scorer's wrong-state check was **text-only** —
it never inspected the candidate DOMAIN's real location. A wrong-state row is not "low quality", it is
**wrong** (emails a different region's org). Fixed so wrong-state prospects are rejected or flagged. ~0 billed
(all cached). ADR-020; audit `docs/wrong-state-audit.md`.

### What was done

- **Diagnosis** (`docs/wrong-state-audit.md`): 8 of 83 S19 rows are wrong-state, in 3 buckets — (1) a domain
  that encodes a contradicting state (`wyomingcountyny.gov` = Wyoming County, **New York** — its page is full
  of "Wyoming", so text-only passed it *with the target-state bonus*; only the domain reveals NY); (2)
  out-of-state universities (`cornell/memphis/cuanschutz/franklin/pitt/divinemercy.edu`) — no state in a
  `.edu` domain; (3) cryptic out-of-state `.gov` (`dconc.gov` = Durham County NC).
- **`page_detector/geography.py::candidate_state(url)`** (`e15693a`... committed as feat): derive a
  `.gov`/`.us` domain's state ONLY where reliable — state-portal domains + `county{abbr}` suffix. Bare
  `{city}{abbr}.gov` (napa→pa), full-name suffix (portwashington→washington), `.edu`, and cryptic acronyms
  return `None` (they'd misfire). 
- **Scorer enforcement** (`feat: enforce geography in scoring`): domain contradicts target → **hard reject**
  (`wrong_state`); domain-confirmed suppresses the text reject; a **geo-confirmation gate** caps confidence
  to **low** (+`geo_unconfirmed` signal) when NEITHER the domain, NOR strong text (target present and not
  out-mentioned by another state), NOR (county/city) the locality confirms the target.
- **Commits (all sydashir):** `fbaf704` docs: wrong-state diagnosis · `e15693a` feat: add domain geography
  validation · `39f875d` feat: enforce geography in scoring · `81b70e5` test: wrong-state validation coverage
  · `600a919` docs: adr wrong-state validation.

### Verification (billed 0, cached)

- **8 S19 geos re-run:** `wyomingcountyny.gov` → **hard-rejected**; `divinemercy.edu` (VA), was **high** for
  Wyoming → **low**; other `.edu` cases already low. **7 of 8 wrong-state now rejected-or-low** (the worst,
  actively-misleading high-confidence case eliminated). Residual: `cuanschutz.edu` (CO) still medium — its
  page incidentally names California/Los Angeles (text confirmation can be fooled; not domain-derivable, so
  not hard-rejectable without a university→state dataset). False positive: `plano.gov` (a correct Texas
  city) medium→low — demoted (flagged), not removed; the accepted precision cost.
- **5-geo baseline re-check:** contact-trust **high still 6, medium still 18 — no legitimate row lost or
  demoted** (low-trust 44→42); the gate additionally rejected two genuine wrong-state candidates for the
  Orange County *California* geo — `orangecountync.gov` (NC) + `orangecountyva.gov` (VA), both
  high-confidence. Net: it improved the baseline, not degraded it.
- **370 tests** (344 + 26 new), pyright 0, ruff+format clean; CLI/scheduler load; master Sheet untouched;
  frontend builds.

### Verdict

Wrong-state is **materially controlled**: the highest-value class (a place named after a state, in a
different state — high confidence, actively misleading) is now hard-rejected, and out-of-state candidates
that can't confirm the target are demoted/flagged. Precision preserved (rejection needs domain proof; the
unconfirmable is flagged, never wrongly killed). Ready for the full **64-geo run (~253 billed / ~$3.80)**.

### Gotchas

- A wrong-state place can be NAMED after the target state (`wyomingcountyny.gov`) — text is actively
  misleading; the domain is the only truth.
- Only assert domain geography where genuinely derivable (portal + `county{abbr}`); bare `{city}{abbr}` and
  full-name suffixes misfire (napa→pa, portwashington→washington).
- `.edu` carries no state — an out-of-state university whose page mentions the target incidentally can still
  slip at reduced confidence; that's a known limit, not a bug.

## 2026-07-06 — Session 21: full production run — the real dataset

The real build. Pipeline is scale-tested (S19) + wrong-state-hardened (S20); this ran the FULL live geo
corpus to create the client's production dataset in Postgres + the master Google Sheet. Deliberate, approved,
one-time spend, capped so a bug couldn't overspend.

### Numbers

- Pre-flight recon (billed 0): 72 live geos, 56 new-billable, projected **223** (below the ~253 S19 estimate).
- **Cost: 223 billed** (~$3.35), hard cap 320 never threatened.
- Funnel: 72 geos → **1,754 candidates → 637 detected → 622 unique prospects** (deduped website+geo);
  5,114 fetches (3,320 httpx / 533 Playwright); **0 whole-geo failures** (per-geo isolation held).
- Quality (622 rows): trust **high 77 / med 146 / low 399**; conf high 298 / med 179 / low 145;
  **email 62% / phone 90% / population 88%**; 82 competitor-linked; AH 393 / MHD 229.
- **Wrong-state gate (S20) fired 21× on real data** — 21 out-of-state candidates hard-rejected.
- Rejections: 497 (incl. 21 wrong_state), 632 fetch-failed (external WAF/DNS noise ~36%).
- **Playwright spot-check 8/8 geo-correct**; 3 high-trust = real university counseling centers with
  same-domain emails; uwyo.edu (the legit WY school S20 kept) present; weak picks (scuhs news page,
  edd labor-market) honestly ranked medium/low.
- Idempotency: re-write appended **0** to the Sheet; DB stayed 622.

### Written to (production)

- Postgres: clean rebuild → **622 prospects (run #8), 72 geos** (was 68/6/5 dev baseline).
- master Google Sheet: **replaced → 622 rows** (was 68 baseline rows).

### Incident + recovery (honest)

The ~2-hour run outlasted the host: Docker/Postgres stopped mid-run, so the DB + Sheet writes failed AFTER
the pipeline completed. The DB write is one atomic delete-then-persist transaction (never committed → DB
safe); the Sheet write is sequenced after it (never ran → Sheet untouched); the pipeline had already written
a **CSV backup**. Recovery: restart Docker, then `finalize_production_s21.py` re-wrote the 622 already-
computed rows from the CSV to DB + Sheet with **zero re-spend**. The atomic transaction + CSV-first backup
saved it. Lesson: keep the host awake (or persist incrementally) for multi-hour runs.

### Nothing broke

No `src/` changes this session (only scratch scripts + the run). **370 tests** green, CLI/scheduler load,
frontend unchanged. Commits (sydashir): `45bab24` docs adr, plus this progress log.

### Verdict

Production dataset is **demo-ready**: 622 real, geo-correct, quality-ranked prospects across all 72 geos, live
in the DB (SaaS app) + master Sheet (outreach). Remaining is operational hardening: frontend tests, run
monitoring/alerting, outreach-status tracking.

## 2026-07-07 — Session 22: Phase F3 — outreach status tracking

Made AuthorityScout a tool the team WORKS IN, not just a prospect list: mark a prospect
contacted/responded/interested/etc. + notes. DB → API → UI. 0 billed (feature work on the existing 622-row
dataset). ADR-022.

### The make-or-break (ADR-022)

Outreach status is USER-entered data on the same row as PIPELINE-generated discovery data. A pipeline re-run
upserts prospects and must NOT overwrite the team's status/notes. Solution: the outreach columns are absent
from `upsert_prospect`'s INSERT values AND its `on_conflict set_`, so a re-run structurally can't touch them
(defaults on insert, preserved on conflict). Pinned by a real-Postgres test + proven end-to-end.

### What shipped (commits, all sydashir)

- `b8ae75c` feat: add outreach status schema — `OutreachStatus` enum + 5 user-owned columns
  (outreach_status default not_contacted / notes / contacted_at / updated_at / updated_by) + Alembic
  migration (622 rows backfilled to not_contacted, discovery intact).
- `c610c2f` feat: preserve outreach fields on pipeline upsert — explicit preservation + `update_outreach_status`
  (records the user, stamps contacted_at on first action) + outreach filter + stats breakdown; the make-or-break test.
- `f14146d` feat: add outreach status api — `PATCH /prospects/{id}/outreach` (auth email = updated_by),
  `?outreach_status=` filter, ProspectOut + StatsOut extended.
- `b68434c` fix: reload prospect after outreach update — live-caught 500 (updated_at onupdate → expired attr →
  async-illegal lazy load in model_validate); `session.refresh` after commit.
- `f33b5b1` feat: add outreach status to table — status pill column (sortable), status filter, dashboard card,
  typed client (`patchOutreach`) + `useSetOutreach` mutation + badge CSS.
- `0886461` feat: add outreach controls to detail drawer — editable status dropdown + notes + save
  (→ PATCH, pill/toast, who+when).
- `8d354a6` docs: adr outreach tracking + this progress log.

### Verification (0 billed)

Migration: 622 rows default not_contacted, discovery 100% intact. Live (real DB, minted session, Playwright):
drawer status change → persists, pill → Contacted, dashboard card live "1 · 621 to go", updated_by = the
signed-in user; filter works; unauthorized PATCH → 401. Make-or-break proven at the repository level AND
end-to-end through the pipeline's real `upsert_prospect` (status + notes survived, discovery updated).
**381 tests** (370 + 11), pyright 0, ruff clean; CLI/scheduler + master Sheet write unchanged; frontend
builds + lints clean. Dataset left pristine (622/622 not_contacted).

### Decisions

- **Sheet stays discovery-only** — the DB/app is the outreach source-of-truth; folding user data into the
  pipeline's OutputRow would blur the ownership boundary. OutputRow untouched → master write byte-identical.

### Gotchas

- After an UPDATE, a server-side `onupdate=func.now()` column is expired; serializing the ORM row with a sync
  `model_validate` triggers an async-illegal lazy load → 500. `await session.refresh(row)` after commit.
- The Docker Python SDK can't reach Docker Desktop's socket in this sandbox → testcontainer tests skip/error
  here (they pass in isolation + groups + CI); verified the logic against the real dev Postgres instead.
- Docker daemon drops during long idle/sleep in this environment — restart + `docker compose up -d postgres`.

### Addendum — UI elevation pass (design polish)

On request ("improve the UI/UX to the extreme"), did a cohesive visual-elevation pass on AuthorityScout —
no logic touched, pure presentation. Grounded via the ui-ux-pro-max skill (confirmed the existing direction:
data-dense dashboard, dark-OLED, teal accent). Elevated the SHARED token/primitive layer so every screen
lifts at once: an elevation system (soft layered shadows + `.card`/`.card-interactive` hover-lift), deeper
OLED dark surfaces so panels float, an ambient brand aurora on the app bg, a brand focus-ring, thin themed
scrollbars, `prefers-reduced-motion` respect, and pill-shaped badges. Hero upgrades: stat cards now float
with teal icon-chips + tighter numerals + hover lift; the sidebar active item gets a teal accent bar; the
table panel + rows gain elevation + smooth hover; and the **login is now a premium dark screen** (OLED bg +
teal aurora glow + branded logo chip + floating card). Frontend builds + lints clean (0 warnings); all Phase
F3 functionality intact. Commit (sydashir): `a7b45ac`.

## 2026-07-16 — Session 23: Phase F4 — frontend tests + error monitoring

Final hardening before hosting. Closed two production-readiness gaps: the React app had ZERO tests
(backend had 381) and production failures alerted no one. No features, no visual change, 0 billed,
622-prospect dataset untouched. ADR-023.

### Part A — frontend tests (Vitest + RTL + MSW)

- Test infra: Vitest (jsdom, globals) in the Vite config, MSW v2 intercepting the API at the network layer
  (real client/hook/component logic against realistic shapes, not stubbed hooks), `npm test`.
- **30 tests** (9 files), REAL behavior not coverage theater: api client (filter/pagination params on the
  wire, parsing, ApiError, PATCH/POST bodies); auth gate (401→login / authed→app / logout) + login 403
  message; prospects table (rows, trust sort, column hide, select); filters (param + subset render, empty,
  error); drawer + outreach (chips, clipboard, outreach PATCH → pill flip + toast, error path); runs +
  Run-now (POST site+mode, error); ErrorBoundary (crash → recovery screen). Not tested: pure visual styling,
  the real Google GSI iframe (its 403/success handling IS tested).

### Part B — error monitoring (Sentry, DSN-gated, silent in dev)

- Shared core `authority_finder/monitoring.py` (init + scrub); `backend/monitoring.py` adds FastAPI/Starlette
  integrations; `frontend/src/lib/monitoring.ts` for React.
- Backend captures unhandled exceptions AND — critically — background-run failures: `execute_run` (API task)
  and the scheduler's `run_tick` per-site failure (the 3am scheduled-run case); the scheduler CLI inits
  Sentry so the Docker cron reports too.
- Frontend `@sentry/react` ErrorBoundary → on-brand recovery screen (not a white page) + report; errors only
  (no tracing/replay).
- Gating: SENTRY_DSN / VITE_SENTRY_DSN blank = disabled (dev + tests silent, CI sends nothing).
- Scrubbing: send_default_pii=False (denies auth/cookie/session/token/secret) + before_send drops
  cookies/body/sensitive-headers + redacts prospect emails. Session/JWT/.env/emails never leave the process.

### Verification (0 billed)

Frontend 30 tests green + build + oxlint clean. Backend **387 tests** (381 + 6 monitoring): scrub_event
strips cookies/body/headers + redacts emails; init_sentry disabled with no DSN; execute_run captures a
background failure; ErrorBoundary fallback proven by a crashing-child test. Nothing broke: db+api pass with
the monitoring-wired app, CLI/scheduler + master Sheet unchanged, 622 dataset untouched (622/622
not_contacted). Commits (sydashir): `064c355`/`db0654b`/`b19b355`/`0cb2bea` (tests), `1e3675b`/`ef3f0b8`
(monitoring), `16ef384` (adr), + this progress log.

### Hosting-time (Phase E)

Create two Sentry projects (Python + React); set SENTRY_DSN/SENTRY_ENVIRONMENT (API/scheduler) +
VITE_SENTRY_DSN (frontend build). Monitoring turns on the moment a DSN is present.

### Gotchas

- Vitest 4 + Vite 8: `defineConfig` from `vitest/config` types the `test` block (no triple-slash needed).
- ESM named exports can't be `vi.spyOn`'d — mock the module (`vi.mock('@sentry/react', ...)`).
- Pyright strict flags nested `dict[str, Any]` access as "partially unknown" — `cast(...)` each narrowed piece.
- The npx-installed `.claude/skills/**` vendored Python scripts get linted by `ruff check .` — exclude
  `.claude` in pyproject + gitignore them.
- Docker Desktop kept dropping this session — testcontainer db/api tests skip when it's down, pass when up.
