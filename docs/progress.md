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
