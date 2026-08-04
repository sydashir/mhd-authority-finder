# Architecture Decision Records

Append-only. Newest entries at the bottom. Each ADR captures: decision, alternatives weighed, why we picked what we picked. If a later ADR supersedes an earlier one, link them both ways — never edit history in place.

---

## ADR-001 — Initial stack: Python 3.12 + uv + ruff + pyright strict + async httpx + pydantic-settings + structlog

**Date:** 2026-05-19
**Status:** Accepted
**Context:** Session 1 — scaffolding only, picking the toolchain we will live with for the duration of the project.

### Decision

- **Language:** Python 3.12.
- **Env & dependency manager:** `uv`.
- **Layout:** `src/` layout.
- **Lint + format:** `ruff` (line length 100, target py312).
- **Type checker:** `pyright` in **strict** mode.
- **Test runner:** `pytest` + `pytest-asyncio`.
- **HTTP:** async `httpx`.
- **Config:** `pydantic-settings` reading `.env`.
- **Logging:** `structlog`, JSON renderer.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| `poetry` instead of `uv` | yes | `uv` resolves and installs an order of magnitude faster, has a single static binary (no Python bootstrap chicken-and-egg), and writes a deterministic `uv.lock`. `poetry` is fine but slower and historically flaky on lock resolution for SciPy-adjacent deps. We aren't paying that cost when `uv` is now stable and widely deployed. |
| `pip` + `requirements.txt` + `venv` | yes | No lockfile by default, no native script runner. Reinventing what `uv` already gives us. |
| `pdm` | briefly | Smaller ecosystem and slower than `uv`; no compelling reason over `uv`. |
| Flat layout (`authority_finder/` at repo root) | yes | Picking `src/` layout prevents the "ran tests against the wrong copy of the package because Python imported from CWD" footgun. Costs nothing once configured. Standard for non-trivial libs. ([Hynek Schlawack on src layout](https://hynek.me/articles/testing-packaging/)) |
| `black` + `isort` + `flake8` | yes | Three tools doing what `ruff` does in one binary, slower, more config files. `ruff` now covers formatting too. |
| `mypy` instead of `pyright` | yes | Both fine. Picked `pyright` for: (a) stricter defaults than `mypy --strict`, (b) faster on cold runs, (c) shares the inference engine with Pylance so editor and CI agree. `mypy --strict` would also be acceptable; this is a defensible coin-flip — see "Risk" below. |
| `pyright` non-strict | yes | The whole point of catching mistakes early is that strict catches mistakes early. Non-strict allows untyped function bodies, which defeats the purpose on a greenfield project. |
| Sync `requests` instead of async `httpx` | yes | The workload is dozens to hundreds of outbound HTTP calls per geo across multiple providers. Concurrency is the entire performance story. Async from day one prevents a painful rewrite when we batch geos. |
| Stdlib `logging` | yes | Plain `logging` does not produce structured output without bolting on a JSON formatter, and it leaks `extra=` ergonomics. `structlog` gives typed context binding and JSON for free. Phase 2 we may ship logs to a backend; structured is mandatory there. |
| `python-dotenv` directly | yes | `pydantic-settings` already supports `.env` and gives us a typed `Settings` object validated at startup. One library, one source of truth. |

### Why these specifically

- **Python 3.12** — 3.13 is stable but 3.12 has the broader binary-wheel coverage we need (httpx, pydantic v2 native, Google API client). No 3.13-only feature is on our path.
- **`uv` over `poetry`** — speed (matters for CI), one binary install, deterministic lockfile, and active upstream momentum from Astral. (Astral docs: <https://docs.astral.sh/uv/>)
- **Async-first** — the pipeline is I/O-bound by construction (search API + page fetches + sheet writes). A bounded `asyncio.Semaphore` per provider beats threadpool scheduling for this shape.
- **`src/` layout** — protects against accidental relative imports working in dev and breaking in install. Standard for production Python.
- **`pyright` strict** — strict mode forces every function to be typed and refuses implicit `Any`. Greenfield code is the only time you get to start clean; opting out now means never opting in.
- **`structlog`** — context-bound key/value logging is the right substrate when each pipeline step adds metadata (geo, domain, source). JSON output makes the eventual aggregation step a no-op.

### Risk / open points

- `pyright` strict can be noisy with third-party libs that ship partial stubs. We accept that and use targeted `# pyright: ignore[reportX]` with a written reason rather than relaxing the global config.
- `ruff` and `pyright` versions evolve quickly. Pin them and bump deliberately, with a commit that explains the diff.
- If `mypy` turns out to integrate better with a downstream tool we adopt, swapping is cheap because no source annotations change.

---

## ADR-002 — Commit hygiene: no AI attribution, conventional commits, atomic commits

**Date:** 2026-05-21
**Status:** Accepted
**Context:** Session 2 — tightening rules before any feature code lands.

(Numbering note: ADR-002 lands after ADR-003 chronologically because both were decided in the same session; numbers reflect topic ordering in `CLAUDE.md`'s working-rules section, not commit timeline.)

### Decision

1. **No AI attribution on commits or PRs.** No `Co-Authored-By: Claude`, no "Generated with Claude Code" footer, no emoji robot, no model name in commit metadata. Commits are authored by the human. Globally enforced via `~/.claude/settings.json` (`attribution.commit = ""`, `attribution.pr = ""`).
2. **Conventional-commit style, short.** Subject ≤ 60 chars, lowercase, imperative mood (`add x`, not `added x`). Type prefix from the fixed set: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `build`. Body only when the diff itself doesn't explain *why*. No marketing language. No emojis.
3. **Atomic / commit-by-commit.** One logical change per commit. Two unrelated edits = two commits. If a refactor surfaces a bug fix, that's still two commits. The CLAUDE.md-rules edit and the Hunter-drop edit landed as two commits this session — that's the standard.

### Rationale

- Clean git history is a debugging tool, not a vanity exercise. `git bisect` only works when each commit is one thing. `git revert` only works without collateral damage when each commit is one thing.
- AI attribution in the commit trailer pollutes `git blame`, leaks tooling details into a permanent record, and conflates authorship. The human runs the IDE; the human owns the commit. (Pattern used by [Linus on subsystem maintainers](https://lwn.net/Articles/669976/), and the rationale for the [Conventional Commits spec](https://www.conventionalcommits.org/).)
- Short subject lines render properly in `git log --oneline`, GitHub PR lists, and every code-review UI. Long subjects truncate and lose meaning.
- Atomic commits make code review faster: reviewers can approve or reject a discrete change without untangling it from three other changes.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Keep AI attribution trailers | yes | Pollutes blame; provides no information that isn't already in the file history. |
| Free-form commit messages | yes | Loses the affordances of conventional commits (changelog tooling, type filtering). The cost of imposing structure is one prefix; the benefit is permanent. |
| Squash unrelated work into "WIP" commits and tidy later | yes | "Tidy later" never happens. Easier to write atomic in the first place than to rewrite history. |

### Enforcement

- `~/.claude/settings.json` global override removes the default trailer.
- The three rules are appended to `CLAUDE.md`'s working-rules section so every future session reads them at start.
- Violations are user-correctable via `git commit --amend` before push; if pushed, fix forward rather than rewriting history.

---

## ADR-003 — Drop Hunter.io / Apollo from MVP scope

**Date:** 2026-05-21
**Status:** Accepted
**Context:** Session 2 — re-scoping after the user reviewed the feasibility doc's contact-extraction plan and the actual outreach targets.

### Decision

`contact_extractor` does **direct scraping only** for the MVP. No Hunter.io, no Apollo, no paid email-discovery API. The `HUNTER_API_KEY` field stays in `Settings`/`.env.example` as a dead placeholder for now (cheap, and avoids a future migration); it is not read by any module. If real-world coverage on the first 20–30 outreach geos comes in below ~50%, we revisit.

### Rationale

- The outreach universe is `.gov` and `.edu` — public institutions. These sites are required (formally or by convention) to publish department-level contact info on public-facing pages. The probation-resources page or behavioral-health page is more likely to have a useful inbox than a Hunter lookup of `firstname.lastname@county.gov`.
- For public-institution outreach, a **department inbox** (e.g. `behavioralhealth@countygov.example`) is usually more responsive than a personal employee email. Hunter / Apollo optimise for the wrong target.
- Removing an external API removes a paid dependency, a rate limit, a failure mode, a secret to rotate, and a per-row cost. Net win as long as direct scrape covers the realistic baseline.
- The original feasibility doc cited 65–75% expected coverage assuming Hunter as fallback. Realistically, direct scraping of `.gov` / `.edu` contact pages should land in a similar band; we will measure rather than assume.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Keep Hunter.io as fallback from day one | yes | Adds cost and a dependency before we have real coverage numbers to justify it. Premature optimization for a problem we haven't measured yet. |
| Apollo.io instead of Hunter | yes | Same arguments — wrong target audience (personal emails, not dept inboxes). |
| Drop the env var too | yes | Keeping `HUNTER_API_KEY` as a noted placeholder in `.env.example` costs one line and signals the deliberate "not used yet" state. Avoids a config schema migration if we re-add it later. |

### Trigger to revisit

- Real-world contact-info coverage on the first 20–30 processed geos is below ~50%.
- Or: outreach team reports a specific failure pattern (e.g. dept inboxes go to a black hole, named contacts respond) where Hunter / Apollo data would have changed the outcome.

### Consequences

- `architecture.md` updated (component table, mermaid, scope boundaries).
- The Phase 1 next-step list in `CLAUDE.md` should describe contact extraction as direct-scrape only.
- `Settings.hunter_api_key` exists but is unused. When we revisit, ADR-003 supersession will be added here, not edited in place.

---

## ADR-004 — AH geo URL disambiguation via hardcoded US state-slug whitelist

**Date:** 2026-05-22
**Status:** Accepted
**Context:** Session 3 — building `geo_monitor.url_parser`. Both monitored sites publish their geo pages inside the same Rank Math `page-sitemap*.xml` files as About, Contact, Services, Blog, and other non-geo pages. MHD has a `/serving/` prefix that makes geo URLs trivially distinguishable; AH does not — its state pages live at the root (`/california/`, `/colorado/`), so the regex needed to capture geo URLs (`^/(?P<state>[a-z0-9-]+)(/...)?/?$`) also matches `/about/`, `/services/`, `/blog/`, and every other top-level marketing page.

### Decision

`url_parser.parse_geo_url` validates the captured ``state`` slug against a hardcoded ``frozenset`` of 50 US state slugs (lowercase, hyphenated — e.g. `"north-carolina"`, `"new-hampshire"`) defined in `geo_monitor/states.py`. The check applies to both sites: MHD's regex is strict enough that this is defense-in-depth rather than load-bearing, but the cost of running the check uniformly is zero and it keeps the parser symmetric.

URLs whose `state` slug isn't in the set return `None` from the parser — they are not surfaced to downstream pipeline steps. The fetcher's regex pass already drops most non-matches; the whitelist is the final guard.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| **Blacklist** of known non-geo paths (`/about`, `/contact`, `/services`, `/blog`, ...) | yes | Drifts over time. Every time AH adds a new marketing page we'd ship a code change. Failure mode is silent — a missed entry shows up as a fake "new geo page" in the outreach sheet. |
| **Sitemap post-type filtering** (ask Rank Math for "only WordPress pages tagged 'geo'") | yes | Rank Math doesn't expose post-type / custom taxonomy filters in the sitemap, and the WP team confirmed geo pages are regular Pages with no distinguishing taxonomy. Would need a plugin change on the client side. Out of scope for MVP. |
| **Tighter regex** that requires deeper path (`^/(?P<state>...)/(?P<county>...)/.../?$`) | yes | Loses state-only pages (`/california/`), which the client *does* want included as state-level geos. |
| **Dynamic state list** from US Census API | briefly | Pointless network call for a list that hasn't changed since 1959 and won't unless Puerto Rico is admitted. Adds a dependency, an API key, a failure mode. |
| **Use AH's CMS / Yoast / Rank Math taxonomy data** by scraping each page | yes | Defeats the purpose of using sitemaps for cheap discovery. We'd be paying per-page HTTP cost just to filter the sitemap list. |
| **Include DC + territories from day one** | yes | Neither MHD nor AH currently publishes pages for DC, Puerto Rico, Guam, USVI, American Samoa, or the Northern Mariana Islands. Adding them prophylactically risks accepting nonsense matches (e.g. a `/dc/` slug used for "design changes" or "data center"). Easy to add when needed — one line in `states.py`. |

### Rationale

- The list is bounded (50 entries) and stable on a multi-decade timeline. Hardcoding it is honest about the data; abstracting it would be over-engineering.
- The whitelist applies to both sites for code symmetry and so the parser has a single failure mode regardless of which site fed it.
- The cost of a wrong-direction error matters: a false positive (accepting `/about/` as a geo) corrupts the outreach sheet with a row the team has to manually filter; a false negative (rejecting a real new state slug) is an obvious bug that surfaces immediately when the state page goes live. We optimize for fewer false positives.

### Cost / consequences

- File-level: one constant in `states.py`, one membership check in `url_parser.py`. Zero ongoing maintenance until a US state is added or DC/territories are added.
- Test-level: parser tests pin both the accept cases (50 valid states) and the reject cases (`/about/`, `/blog/`, `/contact/`, `/services/`, `/treatment-programs/`). Live integration test asserts every URL the regex matches on real sitemaps lands in `US_STATE_SLUGS`.
- **Observed in session 3 on AH live sitemap:** the regex matched 68 paths in `/page-sitemap.xml`; only 49 passed the state-slug whitelist. The 19 rejects are exactly the non-geo marketing paths this ADR exists to filter. Working as designed.

### Trigger to revisit

- Client adds DC, a US territory, or any other geo whose top-level slug isn't a real US state name.
- Sitemap structure changes (e.g. client moves to a `/locations/{state}/` prefix on AH) — at that point the URL pattern in `docs/sites.md` changes too and `sites.py` gets updated; the whitelist itself stays.

---

## ADR-005 — Discovery engine: SerpAPI `google_light` page-1, disk cache, classification & dedupe policy, quota guard

**Date:** 2026-06-13
**Status:** Accepted
**Context:** Session 4 — building `discovery/`. Session 4-prep research recommended `engine=google_light_fast` with `num=100` (100 organic results per billed search). The mandatory pre-build validation call returned HTTP 400: *"Google Light Fast engine is no longer available. Please use the Google Light engine instead."* The current `google_light` docs list no `num` parameter at all — pagination is `start` in steps of ~10. Google killed `num=100` upstream in Sept 2025 and SerpAPI's workaround engine has since been retired. Net: **~10 organic results = 1 billed search, on every Google engine.**

### Decisions

1. **Engine: `google_light`, page 1 only** (user-confirmed 2026-06-13). Our queries are tightly targeted (`site:.gov` / `site:.edu` + topic + geo), so page 1 is the precision zone. Page depth is a `start` kwarg on `SerpApiClient.search` — a knob, not a rewrite, if recall proves thin. `engine=google` adds payload we'd ignore at identical billing. Verified live: response carries `organic_results[]` with `position/title/link/snippet` (fixture: `tests/discovery/fixtures/google_light_california.json`).
2. **Direct httpx GET against `https://serpapi.com/search.json`** — the official `serpapi` PyPI client (v1.0.2) is sync-only (`requests`-based); wrapping it in executors loses our async batching for zero gain. Plain GET is a documented first-class integration.
3. **Disk cache, no TTL:** `data/cache/serpapi/{sha256(params minus api_key)}.json`. A cache hit costs zero billed searches, which is what makes dev iteration affordable. No TTL because during dev we *want* frozen SERPs (deterministic reruns); production freshness policy is a later decision. Corrupt cache files read as misses. The api_key is excluded from both the hash input and the cached payload.
4. **Classification policy:** suffix-based via tldextract (offline, bundled PSL snapshot — deterministic, no runtime network): `.gov` → `gov`, `.edu` → `edu`, `.us` → `us_local`, else `other`. **Keep gov + edu + us_local (us_local distinguishable by class for review); drop `other` from candidates but count it** in `DiscoveryResult.counts_by_class` — Phase 2's Ahrefs filter gets sized from measured drops, not guesses.
5. **Dedupe key — state-portal exception** (user-confirmed 2026-06-13): the PSL has no entries under `.gov`, so `dhcs.ca.gov` and `mentalhealth.ca.gov` share registrable domain `ca.gov` — strict registrable-domain dedupe collapses every state agency into one row, observably losing real candidates (fixture positions 1–2). Dedupe therefore uses registrable domain *except* when it's a US state portal (full-name + USPS-code portals derived from `US_STATE_SLUGS`, plus irregulars like `mass.gov`): there the first non-`www` label under the portal is kept (`dhcs.ca.gov` stays distinct). A portal missing from the set degrades to coarser dedupe — never wrong rows.
6. **Quota guard pattern:** `SerpApiClient` counts `billed_search_count` / `cache_hit_count` per session; every billed search is logged (`serpapi.billed_search`) with a running total; the CLI prints billed-vs-cached per geo and per session. Paid tests carry a dedicated `live_paid` pytest marker, excluded from default runs *and* from `-m live` (which stays free sitemap traffic only).

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| `engine=google` paginated | yes | Same billing per ~10 results, slower, richer JSON we ignore. |
| 2+ pages per query | yes | Doubles cost for tail results; page-1 precision is what the templates are designed for. Revisit with recall evidence. |
| Official `serpapi` Python client | yes | Sync-only; an async codebase gains nothing from wrapping it. |
| Cache with TTL | yes | Premature — dev wants determinism; production staleness policy belongs with the scheduler work (Phase 2). |
| Strict registrable-domain dedupe | yes | Spec as originally written; loses state-agency granularity the client's department-level outreach needs. |
| FQDN-minus-www dedupe | yes | No state-agency loss, but county/city portal-vs-www host variants produce near-duplicate rows for manual merging. |

### Live validation evidence (2026-06-13)

5 geos (MD, CO state; FL state; Orange County CA; Newport Beach CA), 19 billed searches, 127 candidate rows. State/county precision strong (e.g. `bha.colorado.gov`, `health.maryland.gov/bha`, `bos4.oc.gov/mental-health-resources`). Observed junk classes recorded in `docs/progress.md` (national domains, same-name wrong-state geos, PDFs, news pages) — input for the Session 5 page detector.

### Trigger to revisit

- Page-1 recall proves thin on real outreach (add `start` pagination).
- SerpAPI retires/renames `google_light` (the Step-2-style validation call should precede any engine assumption).
- Client wants ncala.org-type authority orgs: `site:`-restricted queries can never surface them — Phase 2 needs unrestricted query variants + DR filtering.

---

## ADR-006 — Page detection policy: exclusions, explainable scoring, crawl budget, confidence bands

**Date:** 2026-06-13
**Status:** Accepted
**Context:** Session 5 — building `page_detector/`. The component answers, per discovery candidate: "what is the ONE best page on this domain to reference in outreach, and how confident are we?" Session 4's live run catalogued the failure modes this must handle: federal pollution, same-name wrong-state geos, PDFs, news pages, city-level noise.

### Decisions

1. **Competitor domains are excluded outright** (user-locked). The 16 domains from the brief live in package-level `domains.py` (`COMPETITOR_DOMAINS`) because Phase 2's link checker consumes the same list as its link-target set. They are link-check targets, never outreach prospects — samhsa.gov getting a sheet row would be embarrassing in front of the client.
2. **Federal domains are excluded, drop-but-count** (user-locked) — same instrumentation pattern as discovery's `other` class. `FEDERAL_DOMAINS` is curated (~39 entries): seeded from every federal domain observed polluting Session 4 results, then rounded out with agencies likely to rank for health/justice queries (HRSA, IHS, ACF, BOP, DEA...). Matching is registrable-domain based via tldextract, so `pmc.ncbi.nlm.nih.gov` matches `nih.gov`. Curation rationale: a blocklist is cheap, explainable, and false-negative-safe — an unlisted federal domain just flows to scoring, where geo signals are weak for national sites anyway.
3. **Rule-based explainable scoring, not ML.** Every score decomposes into named `PageSignal`s (topic-in-title +3, topic-in-path +2, resource marker +2, target state +2, locality +1.5, contact affordance +1.5, news marker −3, generic homepage −1.5, thin content −2). Why not ML: no labeled training data exists, the corpus is ~hundreds of pages, the client was promised a *flagging* system (which requires explaining why a row was flagged), and a misclassification costs one manual review — not a model-worthy loss function. Rules also let the outreach team argue with specific weights.
4. **Wrong-state hard rejection** (user-locked scope): count full-state-name mentions across title/h1/meta/text; if another state appears ≥2 times and the target state appears zero times, the candidate is rejected (`wrong_state`) when this happens on the surfaced page or homepage, and the page is merely skipped when it happens on a crawled subpage. 2-letter codes are deliberately not counted ("in", "or", "me" collide with English); "West Virginia" mentions are subtracted from "Virginia" counts.
5. **Crawl fallback with a hard budget of 6 fetches per candidate** (homepage + top-4 keyword-ranked internal links, never leaving the registrable domain). Rationale: the budget bounds worst-case load on government servers (politeness: per-host 2, global 8, robots.txt respected, retries only on transient 5xx); 6 is enough to reach a department page from any homepage we observed, and beyond that the page detector is guessing — low-confidence flagging is cheaper than deep crawling.
6. **Junk-URL nuance:** a PDF/news/search/login *URL* is rejected as the page, but the *candidate domain* survives into the crawl fallback — a good county that surfaced via a PDF still gets its homepage crawled.
7. **Confidence bands:** high ≥ 8.0, medium ≥ 4.5, viability floor 1.5 (below floor → `no_viable_page`). `low` is "flagged for manual review" — the flagging system the feasibility doc promised — not "discard". **Topic-relevance cap** (added after live validation): a page with no topic keyword in title, path, *or* body is capped at `low` regardless of score — an "Animal Services" page cleared medium on services+locality+contact alone. Body-only topic earns a weak `topic_in_body` (+0.5) and escapes the cap (health.maryland.gov/bha is titled just "Get Help"; its body is what proves relevance).
8. **Off-domain redirect rejection** (added after live validation): the final URL after redirects must stay on the candidate's registrable domain. Observed live: `greenfieldca.gov/408/Addiction-Treatment` and `natickma.gov/1551/Drug-Treatment-Resources-for-Veterans` both 301 to `palmerlakerecovery.com` — a private rehab company that would otherwise have entered the outreach sheet under a .gov label, scored 8.5/high.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| ML/embedding-based page classification | yes | No training data, tiny corpus, unexplainable flags, heavier dependency surface. Revisit only if rule precision stalls below the feasibility doc's 70–75% promise after tuning. |
| Geo-relevance scoring instead of a federal blocklist | yes | National domains *do* mention states constantly (medicare.gov lists all 50) — scoring alone under-rejects. Blocklist first, scoring as backstop. |
| Unlimited same-domain crawl | yes | Politeness and wall-clock. The budget makes worst-case load predictable per candidate. |
| Rejecting candidates whose surfaced URL is junk | yes | Loses good domains that surfaced via PDFs — observed repeatedly in Session 4 (bscc.ca.gov, westcliff.edu). |

### Live validation evidence (2026-06-13)

127 candidates across the 5 cached geos → 54 detected (23 high / 21 medium / 10 low), 38 rejected (23 federal, 7 competitor, 3 wrong_state, 3 no_viable_page, 2 junk_url), 35 fetch_failed, 172 page fetches. Blind 20-page accuracy sample (seed 42, high+medium): **high 8/8 correct, medium 5/12, overall 13/20 (65%)** — recommendation: auto-accept high, light-review medium, full-review low. Full breakdown with named examples in `docs/progress.md` Session 5 entry. Dominant fetch-failure mode: WAF/bot 403s against our honest user agent (27% of candidates, including state health departments).

### Trigger to revisit

- Accuracy sample on real outreach batches drops below ~70% — first lever is weight/threshold tuning against the validation corpus, second is query-template refinement, ML last.
- A federal domain repeatedly pollutes results without being on the list — add it (one line).
- Client adds non-US geos (the state-name validator is US-only by construction).

---

## ADR-007 — Contact extraction (direct-scrape) + two-tier httpx→Playwright fetch

**Date:** 2026-06-17
**Status:** Accepted
**Context:** Session 6 — building `contact_extractor/` (feasibility component 5) and resolving Session 5's open issue that 27% of candidates (including state health departments) 403-block our honest user agent. ADR-003 locked direct-scrape only (no Hunter/Apollo). Precision-over-recall is the governing principle: a wrong contact burns sender reputation, so the design biases toward fewer, correct contacts.

### Decisions

1. **Two-tier fetch, shared infra.** The page fetcher (promoted to `authority_finder/fetching/`, used by both the detector and the extractor) tries **httpx first, always**, and escalates to **headless Playwright Chromium only on HTTP 403 or TLS-chain failure**. We never spoof a browser UA on the httpx tier — escalating to a *genuine* browser (which sends Chromium's real UA) is honest, where lying with a fake header from httpx is not. robots.txt is enforced once, before either tier. Hard budget: at most one browser fetch per URL (no Playwright-tier crawling). One browser instance per run, launched lazily on first escalation and reused. If Playwright also gets a hard 403, the row degrades to `fetch_failed` and is flagged — no hanging. Genuine server-side TLS faults (e.g. cdph.ca.gov's missing intermediate) are flagged, not chased.
2. **`phonenumbers` for phones, regex+guards for emails (not `email-validator`).** `phonenumbers` (Google's libphonenumber port, pinned 9.0.32, pure-Python, ships py.typed) is the only correct tool for extracting US numbers from free text via `PhoneNumberMatcher`. `email-validator` was rejected: it *validates* one known address (with DNS deliverability calls by default) — it does not *extract* — so it adds a network dependency for nothing. Emails use a bounded regex plus a false-positive guard list.
3. **Email false-positive defenses** (hardened by an adversarial audit — five lenses generated messy inputs and ran them against the real functions; defects below were reproduced then fixed): non-PSL TLD rejection via tldextract (kills `x@host.local`, `handler@bind.call`-class — though `.call` is a real gTLD and is accepted); placeholder-domain **suffix** match (kills Sentry DSN subdomains like `k@o45.ingest.sentry.io`); template-token stripping (`{{...}}`, `${...}`); numeric-domain-label rejection (version pins `serde@1.0.gov`); asset/code-extension blocklist; placeholder local-parts; `mailto:` trusted over body text; role accounts (webmaster/noreply) deprioritized by confidence, not dropped; dept local-parts (health/info/intake) bumped.
4. **Phone false-positive defenses:** `Leniency.EXACT_GROUPING` + reject pure-digit raw matches (an order/case/ID/tracking number is an *unformatted* valid NANP run) + a record-label context guard (order/invoice/confirmation/case/account/member/ref…). Empirically, leniency alone did not separate IDs from phones; the pure-digit + label guards do, with zero loss on real formatted numbers (incl. fax, toll-free, +1, dotted/spaced/parenthesized).
5. **Multi-segment spelled obfuscation:** `info at mail dot county dot gov` decodes whole to `info@mail.county.gov` (the single-`dot` version truncated to a *wrong* address — worse than a miss under precision bias). County `.us` hosts decode correctly.
6. **Ranking:** expose the full ranked list (outreach may want alternates) but mark one best — by confidence desc, then source trust (mailto > contact_page > body_text), with case-insensitive dedupe.
7. **Contact-page fallback:** when the detected page yields no email, follow ≤2 ranked same-registrable-domain contact/staff-directory links (shared tier → Playwright-eligible), off-domain-redirect guarded. A page offering only an input form → `partial` (still outreach intel), recorded as `has_contact_form`.
8. **Status semantics:** `extracted` (≥1 email), `partial` (phone or contact-form only), `none`, `fetch_failed`.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Spoof a browser UA on httpx | yes | Dishonest, and a real browser clears more WAFs than a fake header anyway. |
| Playwright for every fetch | yes | Orders of magnitude slower; httpx serves the overwhelming majority. Escalate only on 403/SSL. |
| `email-validator` | yes | Validates one address with default DNS calls; does not extract from text. |
| Looser phone leniency only | yes | All leniency levels still accept bare ID digit-runs; structural guards are what work. |
| Drop role/webmaster emails entirely | yes | Sometimes the only public inbox; deprioritize by confidence and let the team decide. |

### Live validation evidence (2026-06-17)

Playwright recovered **14 of 35** Session-5 fetch-failures (40%), incl. floridahealth.gov, cdph.ca.gov (the SSL-chain case), fsu.edu, umd.edu, fmu.edu — detected pages rose 54→67. Extraction over 67 detected pages: **email 49/67 = 73%** (.gov 70%, .edu 75%), **phone 54/67 = 81%** — both above the feasibility doc's 65–75% promise. The 15-email blind quality sample read ~8/15 usable for outreach (harsh: department-relevant) and surfaced one garbled extraction (ZIP+phone glued into the local part) now guarded. Playwright spot-checks confirmed 3/3 extracted email+phone pairs genuinely on-page (no hallucination). Full breakdown in `docs/progress.md` Session 6.

### Trigger to revisit

- Extraction email coverage on real batches falls below ~50% (ADR-003's revisit threshold for reconsidering a paid email-discovery fallback).
- Playwright recovery proves marginal (then drop the browser tier to cut dependency weight) or insufficient (then reconsider UA policy with the client).
- A class of wrong contacts recurs in outreach QA — add the guard, pin the case as a regression test.

---

## ADR-008 — Population (Census, keyed) + output schema + dual CSV/Sheets writer

**Date:** 2026-06-19
**Status:** Accepted
**Context:** Session 7 — the last two Phase-1 components (population, output) plus the first full end-to-end run. The session opened with the plan to use Census *keyless*, but a pre-build check found that contradicts current reality.

### Decisions

1. **Census keyless is dead — use a free key, degrade gracefully without one.** A real keyless ACS call now 302-redirects to `api.census.gov/data/missing_key.html` (the Bureau retired keyless access ~May 2026). The user's "no key" instruction is no longer satisfiable. `population/census.py` therefore takes a `CENSUS_API_KEY` (free, instant signup) and, when it's absent, returns `not_found` for every geo rather than blocking — population is a prioritization aid, never a row blocker. `census_api_key` was re-added to `Settings` (optional, default empty) after Step 0 had removed it on the now-invalid keyless premise.
2. **Dataset: ACS 5-year, vintage 2024**, variable `B01003_001E`, base `https://api.census.gov/data/2024/acs/acs5`. ACS5 is the only dataset with complete place-level (city) coverage in one uniform 3-level query. State → direct FIPS (static 51-entry map). County/city → one cached wildcard fetch per state (`for=county:*`/`for=place:*&in=state:FIPS`, which returns the population inline), then client-side fuzzy match.
3. **Fuzzy-match-and-flag, never guess wrong.** Names are normalized (drop `, State` tail + type suffix `city`/`County`/…, NFKD, periods stripped, `st`↔`saint`) then matched: exact → `exact`; else `difflib` close-match ≥ 0.86 → `fuzzy`; else `not_found`. Negative ACS sentinels (`-666666666`) → `value=None`. Neighborhood slugs that aren't Census places (e.g. `downtown-los-angeles`) honestly return `not_found`. `rapidfuzz` was rejected to avoid a dependency — stdlib `difflib` is adequate for matching within one state's ~hundreds of places.
4. **Output schema = brief columns, exact order**, plus an 11th internal `Confidence` column so the team can sort by detection confidence (the feasibility doc's flagging system, surfaced in the deliverable). `Competitor Links` is `—` (Phase 2). Every field is a string cell; missing data → empty cell, never fabricated. `build_row` assembles from the chained per-candidate outputs and degrades every hole to blank.
5. **Two write targets, shared dedupe/sort.** CSV (`--dry-run`, no creds) and Google Sheets (live). Both dedupe by `(registrable domain, Geo Served)` and sort by geo → confidence (high→low) → population (desc, unknown last), so the most valuable prospects sit at the top.
6. **Sheets idempotency via read-then-append.** One tab with a Source column (matches the brief; simpler than per-source tabs). Existing rows are read first and input is deduped against them by `(Website, Geo Served)`, so re-running never duplicates — idempotent. The google client is sync (httplib2), so the write runs in `asyncio.to_thread`. Failures raise a typed `SheetsError` naming the likely cause (the common one: service account not shared as Editor → 403). Pinned `google-api-python-client==2.197.0` + `google-auth==2.55.0`; the dynamic client is contained behind `Any` so it typechecks clean under pyright strict.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Keyless Census | yes (planned) | Retired ~May 2026; keyless calls redirect to a missing-key page. |
| PEP instead of ACS5 | yes | ACS5 has better/uniform place coverage in one variable across all 3 levels. |
| `rapidfuzz` | yes | Extra dependency; stdlib `difflib` suffices for per-state place matching. |
| Per-source tabs (MHD/AH) | yes | A Source column on one tab matches the brief and keeps dedupe/append trivial. |
| Block the row when population is missing | no | Violates the golden rule; population is an aid, not a gate. |

### Live validation evidence (2026-06-19)

(Full funnel, the CSV deliverable sample, population coverage, the live-Sheet write + idempotency re-run, and the Playwright deliverable spot-checks are recorded in `docs/progress.md` Session 7.)

### Trigger to revisit

- A `CENSUS_API_KEY` is added → population fills in (no code change needed).
- ACS releases a newer vintage → bump the base URL year deliberately.
- Client wants separate MHD/AH tabs or different columns → the writers take a tab arg and the header is one constant.

---

## ADR-009 — Contact attribution hardening: same-domain constraint + page-confidence vs contact-trust split

**Date:** 2026-06-23
**Status:** Accepted
**Context:** Session 7's live verification exposed two "real contact, wrong target" defects that a single Confidence column couldn't express. WRONG-ORG: body-text email extraction grabbed `info@frsn.org` (a third-party crisis line merely mentioned) onto a `montgomerycountymd.gov` row. WRONG-DEPT: when a dept page and its contact page lacked an email, the fallback hopped to the org's generic contact-us and grabbed `admissions@ucdenver.edu`. Root cause: the deliverable's Confidence rated PAGE detection, not whether the CONTACT belongs to the right org/department.

### Decisions

1. **Domain-constrain body-text contacts.** Body-text-regex emails are kept only when their registrable domain (tldextract) matches the page's — a third-party email mentioned in body text is dropped, not ranked. `mailto:`/`tel:` (intentional links) and contact-page hops are exempt (the link/hop is itself the trust signal). Phones have no domain, so body-text phones are kept but demoted below `tel:` (already the ranking). This kills the frsn.org class.
2. **Page confidence ≠ contact trust — split them.** The existing `Confidence` column keeps rating page detection. A new **Contact Trust** band rates the contact: `high` = same-domain `mailto:` with a dept-relevant local-part (health@, behavioralhealth@, counseling@, contact@, info@); `medium` = same-domain `mailto:` (generic) or a dept-relevant contact-page hop; `low` = generic contact-page hop (e.g. admissions@), phone-only, or no contact. This is what answers "can outreach trust this contact" — the question Confidence was wrongly being asked. The ucdenver admissions@ case now reads `low`.
3. **Contact Source as a deliverable column.** Surface each contact's provenance — "mailto (same-domain)", "mailto (off-domain)", "body-text (same-domain)", "contact-page hop", "tel" — between Phone and Description, so outreach sees per-row trust at a glance. (Live: the frsn.org defect turned out to be a *cross-domain mailto* link to a third-party org, not body-text — it can't be domain-dropped without also losing legitimate sibling-gov mailtos like `fourth.district@ocgov.com` on `oc.gov`, so it's labelled "mailto (off-domain)" and banded `low` — flagged, not silently shown as trusted.)
4. **Sheets schema migration.** Inserting the two columns shifts Geo Served's index, so a sheet holding the old layout is **cleared and rewritten** on header mismatch (the rows were generated by us; mixing layouts would misalign columns and break (Website, Geo Served) dedup). Steady-state stays append-only idempotent at the new layout (Geo Served at index 7).

### Why "real but mis-attributed" is the precision risk that matters

A blank cell costs nothing; a confident-looking wrong contact gets emailed and burns sender reputation with the wrong org. Precision-over-recall (ADR-003/007) means we'd rather drop a body-text email of uncertain ownership than present it as the row's contact. The same-domain constraint + trust band make the residual visible rather than silent.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Constrain mailto/contact-page too | yes | They're intentional (the org put the link/page up); over-constraining drops real cross-domain contacts like `fourth.district@ocgov.com` on `oc.gov`. |
| Drop generic contact-page emails entirely | yes | Sometimes the only inbox; flag as `low` trust and let outreach decide. |
| Append the new columns at the end (no migration) | yes | The brief wants Contact Source next to Phone for readability; a one-time clear+rewrite of our own rows is clean. |
| Reuse the single Confidence column | no | That conflation is the root defect. |

### Live validation evidence (2026-06-23)

Re-ran the 5 cached geos to the live sheet, billed_searches=0. Body-text foreign-domain emails dropped; ucdenver `admissions@` → `low`; the frsn.org cross-domain mailto → "mailto (off-domain)" / `low`. Contact-trust distribution over the 68 rows: **high 1 / medium 27 / low 40** (the cross-domain-mailto fix moved 10 rows medium→low). Schema migration + replace-mode refresh both clean; append re-run idempotent (0 added). Full detail in `docs/progress.md` Session 8.

### Trigger to revisit

- A wrong-org contact still slips through (tighten body-text or extend the constraint to suspicious mailto domains).
- Outreach reports the trust bands don't match their experience → recalibrate the dept local-part set / banding.

## ADR-010 — Contact quality: department-directory discovery + dept-relevance ranking & band re-derivation

**Date:** 2026-06-24
**Status:** Accepted
**Context:** Session 8 made contact *attribution* honest (same-domain constraint + trust band), but the live distribution exposed the real ceiling: **high 1 / medium 27 / low 40** over 68 rows. A Step-1 diagnosis (`docs/contact-quality-audit.md`, re-run at `billed_searches=0`) found page detection is strong but contact quality is weak, and quantified *why*: the ranker was **not** mis-picking among emails already on the page (bucket B = 0); a large part of the apparent "unfixable" tail was real department mailboxes the **narrow** Session-8 dept dictionary failed to recognise (`recoverysupport@`, `ivccounseling@`, `humansvs@`, `counselinf@`); and **23 / 68 rows (34%) publish no same-domain email at all** — a structural ceiling no code can lift. The goal was to raise *trustworthy* contacts without relaxing the bands.

### Decisions

1. **Department-directory discovery.** The contact-page hop now fires unless the detected page already holds a same-domain **department** inbox (a generic `info@` no longer suppresses it), and stops as soon as a department contact is found. Link ranking (`find_contact_links`) switches from summed keywords to a single best-match weight and ranks staff/department-directory and MH-topic links **above** a generic "contact us", so the hop reaches the actual department. Budget unchanged (≤2 extra fetches), shared httpx→Playwright tier (recovers soft-blocked WAF pages).
2. **Department-relevance classification + ranking.** A single evidence-derived classifier (`classify_localpart` → `dept` / `role` / `generic` / `other`) is the source of truth, with an `environmental`/`developmental`/`governmental` guard checked first (`environmentalhealth` contains `mentalhealth`). A same-domain department inbox now ranks ahead of any non-department email regardless of source confidence; role/wrong-dept local-parts take a confidence penalty.
3. **Trust bands re-derived — TIGHTENED, not loosened.** Off-domain → `low`; **role / wrong-department → `low` even as a same-domain mailto** (`admissions@`, `communications@`, `webmaster@`, `auditor@`…); same-domain department inbox → `high` (mailto) or `medium` (reached via a hop / body); generic `info@`/`contact@` → `medium` as a mailto (never `high`), else `low`; phone-only → `low`. This *demotes* the old lone `high` (`info@csupueblo.edu`) to `medium` and demotes ~11 over-trusted mediums to `low`. We explicitly narrowed what counts as trustworthy.
4. **Phone-glue guard.** Reject email local-parts with a formatted phone number glued in (`303.458.3558counseling@…`, `724-8859smhservice@…`) — the live re-run surfaced these; the existing `\d{5,}` run-guard misses them because separators break the run.

### Why a smaller "high+medium" is the correct outcome

A wrong or garbled contact emailed in good faith burns sender reputation; a blank costs nothing. The old `medium` counted *every* same-domain mailto, including wrong-department inboxes, so the headline overstated trust. After tightening, **high+medium falls (28→24) while quality rises** — `high` is now 6 verified department mailboxes rather than 1. We report that drop as a feature, not a regression.

### The honest ceiling (bucket-D reality)

23 / 68 rows have no same-domain email anywhere (19 phone-only, 4 none); adding off-domain-only sites, **~40% of authority pages publish no own-domain contact**. The directory finder's *measured* real lift is ~2 rows — most sites simply don't expose a department email to reach. For that ~40%, phone + page URL is the deliverable. No part of this ADR changes that.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Feed page topic/Confidence into Contact Trust | yes | Re-merges the page-vs-contact split ADR-009 deliberately made; relevance already lives in the Confidence column. |
| Drop off-domain / role contacts instead of banding `low` | yes | Precision-over-recall = flag, don't delete; outreach may still want the only inbox a page offers. |
| Broaden the dept dictionary but keep role inboxes at `medium` | no | That inflates the aggregate without improving trust — the opposite of the goal. |
| Bare `health` substring as department | no | Matches `environmentalhealth`/`healthinspector` (food/restaurant inspection); kept as an exact match + guarded stems. |

### Live validation evidence (2026-06-24)

Re-ran the 5 cached geos, **`billed_searches = 0`** (361 fetches, 261 httpx / 57 playwright). `replace=True` rewrote **68 rows**; idempotent append re-run added **0** at the 13-col layout. **Contact-trust distribution: high 1→6 / medium 27→18 / low 40→44.** 10 promotions (6 to `high`, all genuine department mailboxes — incl. `montgomerycountymd.gov` off-domain `info@frsn.org` → same-domain `frs.peer_support_cism@…`; 4 to `medium` via directory hops), 11 demotions (precision corrections). The 6 `high` rows were Playwright-verified in a real browser: each contact is a same-domain `mailto:` on a department-relevant page, no fabrication.

### Trigger to revisit

- Outreach finds department mailboxes still missed → extend the dept stem set from new evidence (keep the env/dev guard).
- A role/wrong-dept inbox still reads `medium` → add the local-part to the role set.
- The structural ~40% needs coverage → that is a sourcing problem (phone/forms), not a ranking one; consider capturing contact-form URLs as a distinct deliverable field.

## ADR-011 — Competitor backlink detection (link_checker, component 6)

**Date:** 2026-06-24
**Status:** Accepted
**Context:** The brief's component 6 fills the previously-blank "Competitor Links" column: for each authority page in the sheet, does that `.gov`/`.edu` site link OUT to any of the 16 `COMPETITOR_DOMAINS`? A site already linking to a competitor directory is a warmer prospect (it lists directories) and tells outreach which competitor to position against. Precision is paramount — a wrong "links to competitor X" flag misleads positioning, so the bar is precision over recall (ADR-003/007/010).

### Decisions

1. **Which pages to check — mode (b): the detected page + ONE resources page.** Directories of external orgs (and thus competitor links) live on a "resources / links / community partners / helpful links" page far more often than on the detected department page (live: `orangecoastcollege.edu`'s competitor links were on its "Helpful Hotlines and Links" page). So we check the detected page and, if present, follow ONE same-domain resources/links link (`find_resources_link`, single-best-match keyword weighting, same junk/own-domain discipline as the contact-page picker). **Budget ≤2 fetches/candidate.** Recall tradeoff vs a deeper crawl (option c): a competitor link buried 3+ clicks deep, or on a second resources page, is missed — accepted for politeness (these are government sites) and speed; option (a) detected-page-only was rejected because it misses the resources-page directories that are the common case.
2. **Match on registrable domain only — reuse, don't reinvent.** Matching is `registrable_domain(url) in COMPETITOR_DOMAINS` (tldextract, the exact primitive behind `domains.is_competitor`), so `rehabs.com` matches `www.rehabs.com/florida` and `florida.rehabs.com` but **not** `rehabsomething.com` (the substring trap). Relative / scheme-relative hrefs are resolved against the page's `final_url` (`urljoin`) before extracting the domain; links to the candidate's own registrable domain are skipped; identical `(domain, url)` links are deduped. Each match keeps its anchor text + found-on URL for human QA.
3. **Output.** "Competitor Links" was already a column (ADR-008, index 9, placeholder `"—"`); this populates it with `"; ".join(unique competitor domains)` (e.g. `"findtreatment.gov; samhsa.gov"`), `"—"` when none. **No schema change** — Sheets idempotency stays keyed on `(Website, Geo Served)`, so populating the column does not re-trigger appends; the value refresh onto existing rows uses `replace=True` (append-only can't update cells, ADR-009).
4. **Re-fetch, not reuse (for now).** The link checker re-fetches the detected page rather than threading the `PageContent` already fetched in detection/extraction — consistent with the existing detect→extract re-fetch pattern. `check_links_for_candidate` accepts an optional `content=` to skip that fetch, so a future pass that threads `PageContent` through all stages can drop the re-fetch with no interface change. Pipeline-level `return_exceptions=True` isolates a per-candidate fetch failure as `checked_ok=False` → `"—"`.

### Why precision is the bar

A blank cell costs nothing; "links to recovery.com" emailed to outreach as fact, when it doesn't, sends them to position against the wrong competitor. Registrable-domain matching + relative-URL resolution + own-domain skip keep false positives near zero (live: 4/4 flagged rows Playwright-verified, 0 false positives).

### Honest recall limits (what this can miss)

- **JS-injected links** on a page served by the httpx tier (the Playwright tier only runs on 403/SSL escalation) — a competitor link added by client-side JS on an otherwise-200 page is not seen.
- **Deep pages** beyond the detected page + one resources hop (mode b).
- **The `MAX_LINKS=500` parse cap** — a page with >500 anchors (live: `howardcountymd.gov` had 1,416) only exposes its first 500 to the checker; a competitor link past #500 is missed (here there were none).
- **Only ONE resources page** is followed; a second directory page is not.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| (a) Detected page only | yes | Misses the resources/links pages where external directories actually live. |
| (c) Shallow crawl (N pages) | yes | More fetches + load on government sites for marginal recall; (b) catches the common case at ≤2 fetches. |
| Substring / `in url` matching | no | `rehabs.com` would match `rehabsomething.com` — the exact false-flag we must avoid. |
| Add a 14th column | no | "Competitor Links" already exists (ADR-008); this is a value fill, no migration. |

### Live validation evidence (2026-06-24)

5 cached geos, **`billed_searches = 0`**, 484 fetches (364 httpx / 75 playwright). **8 of 68 rows link to a competitor; 11 competitor links total** — by domain: `samhsa.gov` ×8, `findtreatment.gov` ×1, `addictioncenter.com` ×1, `treatmentatlas.org` ×1. `replace=True` rewrote 68 rows with the populated column; idempotent append re-run added 0. Playwright-verified 4 flagged rows in a real browser (cityoffrederickmd.gov → SAMHSA + findtreatment.gov; ndm.edu → addictioncenter.com; orangecoastcollege.edu → treatmentatlas.org + samhsa.gov; montgomerycountymd.gov → samhsa.gov national-helpline) — **0 false positives** — and 2 unflagged rows (howardcountymd.gov: 0 of 1,416 anchors; unco.edu: 0 of 105) — **no under-detection**.

### Trigger to revisit

- Outreach reports missed competitor links → raise `MAX_LINKS`, follow >1 resources page, or add a shallow crawl for high-value geos.
- A competitor domain is added/removed from the brief → update `COMPETITOR_DOMAINS` (single source of truth).
- JS-injected competitor links matter → make the link check Playwright-eligible regardless of status (cost tradeoff).

## ADR-012 — Scheduled auto-triggers: incremental run mode, in-process scheduler, safety caps, Docker

**Date:** 2026-06-25
**Status:** Accepted
**Context:** The final Phase-2 piece: run the pipeline on a schedule, processing geo pages as they're published instead of by hand. SerpAPI is paid, so the failure mode to design against is a runaway scheduled job re-processing the whole geo set and burning quota. It must also run identically on the user's Mac today and a cloud box later, with no code change to move hosts.

### Decisions

1. **Incremental "new geos only" run mode — the cost-safety core.** A scheduled run detects newly-published geos via the existing sitemap diff and runs the full chain for **only those**. To make this safe, the monitor's detect step was split from its persist step: `diff_sitemap` fetches + parses + diffs without writing state (`run_monitor` is now `diff_sitemap` + save, behaviour unchanged); the incremental runner persists state **only after a successful run, and only for the geos it actually processed**. So zero new geos ⇒ zero SerpAPI spend, zero writes, no state change; and a crash or abort mid-run never marks a geo "seen" (it retries next tick). Idempotent sheet append on `(Website, Geo Served)` means a re-run adds nothing.
2. **In-process APScheduler (3.x `AsyncIOScheduler`) over system cron.** One command (`schedule`) runs identically on a laptop and in a container — no host-level cron to configure per environment. It's async-native (the job is an `async def` awaited on the same loop), supports run-once-on-start (`next_run_time=now`), overlap guard (`max_instances=1`, `coalesce`), and graceful SIGINT/SIGTERM shutdown. Pinned `APScheduler>=3.11,<4.0` — 4.0 is still alpha with a different, unstable API. A `--once` flag runs a single tick and exits (cron / smoke test).
3. **Two safety rails.** `MAX_NEW_GEOS_PER_RUN` (default 25) caps the batch — if a site re-publishes its whole sitemap, the overflow is deferred to the next tick (logged loudly), never blowing quota in one shot. `MAX_BILLED_SEARCHES_PER_RUN` (default 150) is a circuit breaker: `SerpApiClient(max_billed=…)` raises `QuotaExceededError` **before** the over-budget billed search; that error is a distinct type (not a `SerpApiError`, so `discover_for_geo` doesn't swallow it) that `discover_many` **re-raises**, so it propagates out of `run_pipeline` and the incremental runner aborts **without saving state**. Both sites run per-tick with per-site isolation.
4. **Docker: one image, secrets mounted, state persisted.** Single-stage `python:3.12-slim-bookworm` + uv (pinned `0.11.15`) + the explicit Debian-bookworm chromium apt deps + `playwright install chromium` (invoked via the venv binary, not `uv run`, so it doesn't try to build the not-yet-copied project), non-root user. Secrets (`.env`, `service-account.json`) are **mounted read-only at runtime, never baked into a layer** (the ADR-008 leak lesson). `./data` is **bind-mounted** so the SerpAPI cache + monitor state survive restarts — a restart never re-processes already-seen geos. Containers can't use chromium's setuid sandbox, so `PLAYWRIGHT_NO_SANDBOX` flips a config-driven `--no-sandbox` (off by default on a normal host).

### Why bind-mount `./data` rather than a named volume

A named volume starts **empty**, so a fresh container would see every geo as new and re-process the entire backlog on first run (capped at `MAX_NEW_GEOS_PER_RUN`/tick, but still spend) and couldn't reuse the existing SerpAPI cache. A host bind-mount persists state across restarts **and** reuses the existing cache + known-geo state — directly serving the cost-safety goal and enabling a true zero-spend no-op tick. A named/cloud volume remains the host-decoupled alternative; it just needs seeding (or it processes the backlog, capped).

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| System cron | yes | Host-specific setup; doesn't move between Mac and a container unchanged. |
| Persist state before processing | no | A crash would mark geos "seen" and skip them forever — the opposite of cost-safety. |
| No caps / no circuit breaker | no | A re-published sitemap or a query explosion would burn quota unbounded. |
| Bake secrets into the image | no | A secret in an image layer is a leak (ADR-008); mount read-only instead. |
| APScheduler 4.0 | no | Still alpha, unstable API, no migration guarantee. |

### Live validation evidence (2026-06-25)

- **No-op tick** (host, current state): both sites `new=0`, **`billed_searches=0`, `rows_written=0`**, `aborted=[]` — proves quiet days cost nothing.
- **New-geo simulation**: removed one known geo (`…/orange-county/irvine/`) from MHD state, ran one tick → processed **exactly 1 geo**, **`billed_searches=4`** (that geo only, not the 23-geo set), **12 rows** appended to the live Sheet; AH `new=0`; state self-healed and was restored to 23.
- **Docker**: image builds; `docker compose run … schedule --once` runs a tick with structured per-tick logs; a second container run (simulated restart) is again `new=0` — **state persisted, nothing re-processed**.
- **Safety caps**: unit-tested — `MAX_NEW_GEOS` cap+defer, `max_billed` raising `QuotaExceededError`, `discover_many` re-raising it, and the incremental abort-without-save.

### Trigger to revisit

- Move to a cloud host with a managed volume → swap the `./data` bind-mount for that volume (seed it once or accept capped backlog processing).
- The backlog grows large → raise `MAX_NEW_GEOS_PER_RUN` or shorten `RUN_INTERVAL_HOURS` so it clears faster.
- Need horizontal scale / durable scheduling across restarts of the scheduler itself → graduate from in-process APScheduler to a job store or an external trigger.

## ADR-013 — Database foundation: monorepo, Postgres source-of-truth, SQLAlchemy 2.x async

**Date:** 2026-06-26
**Status:** Accepted
**Context:** The repo is becoming a single-customer SaaS (auth + UI + hosting; no billing/multi-tenancy). The proven pipeline stays; a database layer is added *underneath* it. A UI can't reliably read from JSON files + a Google Sheet — it needs relational data with real queries (filter by trust/geo/source, run history). Hard constraint: nothing that currently works may break — the existing CLI pipeline and all ~291 tests stay green; the DB is added alongside the Sheet, not swapped in.

### Decisions

1. **Monorepo layout.** The pipeline stays the core library at `src/authority_finder/`; the persistence layer is a subpackage `src/authority_finder/db/` (`models.py`, `session.py`, `repository.py`, `ingest.py`) so both the pipeline and the future backend import it as one installable package. Alembic lives at the repo root (`alembic/`, `alembic.ini`). Phase B (FastAPI) and Phase C (React) will be **top-level** `backend/` and `frontend/` siblings that import `authority_finder`.
2. **Postgres is the source-of-truth; the Google Sheet becomes an export.** Relational queries, real constraints, and run history can't live in JSON/Sheets. The Sheet is demoted to one output target among others (still written unchanged) — outreach keeps it; the UI reads Postgres.
3. **SQLAlchemy 2.x async + Alembic, driven by psycopg 3.** Modern 2.x declarative (`DeclarativeBase`, `Mapped`/`mapped_column`), `create_async_engine` + `async_sessionmaker(expire_on_commit=False)`. **psycopg 3 over asyncpg**: one driver + one `postgresql+psycopg://` URL serves both the async app and *synchronous* Alembic (no async env.py, no asyncpg SSL/PgBouncer quirks). Versions pinned: sqlalchemy 2.0.51, alembic 1.18.5, psycopg[binary] 3.3.4.
4. **Schema** (from the pipeline's `OutputRow` + domain): `prospects` (every OutputRow column typed; native PG enums `trust_band` for contact_trust + confidence, `source_tag`), `runs` (run history → the UI's run list), `geos` (the monitored geo pages, eventually replacing the JSON state files). A prospect links to its `run` and `geo` (FKs). **The (website, geo_served) dedup key is now a real `UNIQUE` constraint** (`uq_prospect_website_geo`) — DB-level idempotency via `INSERT … ON CONFLICT DO UPDATE`, strictly stronger than the old app-level dedupe (concurrent writers / the future API can't create a duplicate).
5. **Additive integration — opt-in `--persist-db`.** Phase A keeps `run`/`schedule` byte-identical: with no new flag they behave exactly as before (Sheet/CSV only, no DB dependency). `run --persist-db` writes the Sheet/CSV **and** upserts prospects + records the run in Postgres. The bridge (`db/ingest.py`) maps `OutputRow → ProspectIn` so the repository stays pipeline-agnostic. Phase B will flip DB-write to the default once the API/UI is the primary surface.
6. **The persistence layer is tested against a REAL Postgres** (testcontainers spins an ephemeral `postgres:16`), never mocks — a persistence layer mocked is a persistence layer unproven. Tests skip cleanly when Docker is absent.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Keep JSON/Sheet as source-of-truth | no | A UI can't filter/paginate/join over JSON files + a Sheet; relational queries need a real DB. |
| asyncpg driver | yes | Needs an async Alembic env.py + has SSL/PgBouncer quirks; psycopg 3 is one driver for app + sync Alembic. |
| Big-bang swap (DB replaces Sheet) | no | Violates "nothing that works may break"; DB is added alongside, Sheet stays an export. |
| Make `--persist-db` the default now | no | Would change `run`/`schedule` behaviour + add a hard DB dependency to a quick CSV dry-run. Opt-in for Phase A; default in Phase B. |
| App-level dedup only | no | A `UNIQUE` constraint is enforced even under concurrent writers / direct API writes — strictly stronger. |
| Mock the DB in tests | no | A persistence layer must be proven against real Postgres. |

### Live validation evidence (2026-06-26)

(See `docs/progress.md` Session 13.) Pipeline over the 5 cached geos at `billed_searches=0` persisted to Postgres via the production path: prospects loaded into `prospects`, the run recorded in `runs`, geos in `geos`; a second persist of the same rows left the prospect count unchanged (the unique constraint held — DB-level idempotency); a `contact_trust='high'` filter returned the high-trust rows. Full existing suite stayed green; `run --dry-run` (no `--persist-db`) still produces the CSV unchanged.

### Trigger to revisit

- Phase B (FastAPI) needs the repository's read methods — extend `get_prospects` filters / add pagination there.
- The `geos` table should fully replace the JSON state files → migrate the monitor to read/write `geos` (kept in parallel this phase).
- Enum evolution (a new trust band / source) needs a manual `ALTER TYPE` migration (Alembic won't autogenerate it).
- Production deploy → managed Postgres + run Alembic migrations on release, not `create_all`.

## ADR-014 — Backend API: FastAPI over the Postgres source-of-truth, background runs via the runs table

**Date:** 2026-06-30
**Status:** Accepted
**Context:** Phase A (ADR-013) added Postgres + a repository layer. Phase B builds the HTTP API the React UI (Phase C) will consume: read prospects + run history, and trigger pipeline runs. Same discipline — additive, nothing that works breaks, the Google Sheet stays a permanent output. Built and verified standalone (HTTP + tests) before any frontend.

### Decisions

1. **FastAPI app under top-level `backend/`, an app factory + lifespan.** `create_app(settings)` (not a bare module global) so tests build isolated apps and prod serves `backend.app:app`. The async engine + `async_sessionmaker` live on `app.state` via a lifespan context manager and are disposed on shutdown — never a module-level engine (no import-time DB side effects; the engine's lifecycle is bound to the app instance). Routers are one module per resource (`health`, `prospects`, `runs`). `backend/` is a first-party package wired into ruff/pyright/pytest; a `py.typed` marker makes `authority_finder` resolve as typed from the new root.
2. **Request-scoped `get_session` dependency reached via `app.state`.** `get_session` yields an `AsyncSession` from `request.app.state.sessionmaker`; routers/repository commit explicitly (the context manager rolls back on error but never auto-commits). Tests override `get_session` (and `get_sessionmaker`) — ASGITransport skips the lifespan, so no real `DATABASE_URL` engine is built under test.
3. **Pydantic v2 response models with `from_attributes`.** `ProspectOut`/`RunOut`/`GeoOut` validate straight off ORM rows; only scalar FKs (`run_id`/`geo_id`) are exposed — never the lazy `run`/`geo` relationships, so serialization never triggers async lazy-load I/O. Enums serialize to their lowercase `.value` (`TrustBand → "high"`); `SourceTag` keeps `"MHD"/"AH"` (matches the deliverable/Sheet). A generic `PageOf[T]` wrapper carries `items/total/limit/offset`; `total` is a separate COUNT (never `len()` of a paged slice).
4. **Triggering a run is a BACKGROUND job tracked in the `runs` table (Option 1: trigger → run_id → poll).** `POST /runs` opens a `runs` row (`status=running`), commits it, and returns **202 + run_id immediately** — it never blocks on the pipeline. A **FastAPI BackgroundTask** then runs the pipeline and finalizes the row to `success`/`failed`; `GET /runs/{id}` reflects the live status (the UI polls it). Chosen over `asyncio.create_task` (GC-footgun, manual cancellation) and over Celery/a queue (full job infra is overkill for one customer, one process). The trade-off — uvicorn graceful-shutdown can cancel a long task — is covered by a **startup orphan-sweep** that flips any leftover `running` rows to `failed`.
5. **The background task opens its OWN session.** A `Depends(get_session)` session is closed once the response is sent, so the task is handed the `async_sessionmaker` + the run_id (a plain int), never the request session or an ORM object. Success and failure are finalized in **separate fresh sessions** (a pipeline that raised mid-write leaves its own session poisoned, so it is never reused to record the failure).
6. **API-triggered runs reuse the S11 cost-safe path and its rails.** `incremental` mode (default) runs `run_incremental` per site — process only newly-published geos, so a no-new-geos trigger spends **0** and writes 0; `full` mode re-runs every known geo. Both write to **BOTH** the Sheet (permanent output, unchanged) and Postgres (under the run_id), and both honor `max_new_geos_per_run` + the `max_billed` circuit breaker. An endpoint that can burn SerpAPI quota must respect the same breakers as the scheduler.
7. **Endpoints are unauthenticated this phase.** Auth is Phase D — documented here so it isn't mistaken for an omission. CORS allows the React dev origin from a typed `cors_allow_origins` setting (with `allow_credentials`, so it must be explicit origins, never `*`).

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Blocking trigger (run pipeline inside the request) | no | A pipeline run is minutes long; the client would time out. 202 + poll is the right shape. |
| Fire-and-forget (`asyncio.create_task`) | yes | GC can collect the task mid-run; needs a manual task registry + shutdown wiring. BackgroundTasks is framework-native with no GC risk. |
| Celery / RQ / a real queue | no | Full job infrastructure for one customer, one process is overkill. In-process BackgroundTasks + the runs table is enough; revisit at multi-worker scale. |
| Reuse the request session in the background task | no | It is closed after the response — guaranteed `MissingGreenlet`/closed-session errors. Open a fresh session from the sessionmaker. |
| Module-global engine | no | Import-time DB side effects + shared across app instances; breaks test isolation. Bind to `app.state` in the lifespan. |
| Expose `run`/`geo` relationships on `ProspectOut` | no | Lazy-load under async serialization → I/O or errors. Expose scalar FKs; eager-load only if a nested shape is ever needed. |
| Lowercase `SourceTag` on the wire | no | The deliverable/Sheet use `"MHD"/"AH"`; keep the API consistent with them. |
| Make `--persist-db`/DB-write the default now | deferred | Still opt-in on the CLI; the API is the DB-first surface. CLI default flip is its own change. |

### Live validation evidence (2026-06-30)

(See `docs/progress.md` Session 14.) App boots under uvicorn; `/health` returns DB-ok against the dev Postgres; OpenAPI 3.1 + `/docs` generate. `GET /prospects` → **68** rows; `?contact_trust=high` → the **6** high-trust sites; `?source_tag=AH` → 23; pagination pages distinctly with a stable total; `/prospects/{id}` renders every column (enums + ISO dates), missing id → 404. `GET /runs` → the recorded runs, newest first; `/runs/{id}` detail; missing → 404. `POST /runs {site:both, mode:incremental}` returned **202 + run_id** immediately; polling showed `running → success`; on **0 new geos** (confirmed by a free sitemap diff first) it spent **billed=0**, wrote 0 rows, and left the 68 prospects untouched — the cost-safety holds on the API path. 318 tests green (291 + 27 db/api), pyright strict 0 errors, ruff clean; `run`/`schedule` CLI + the Sheet write unchanged.

### Trigger to revisit

- **Auth (Phase D):** protect every endpoint; the trigger endpoint especially (it can spend quota).
- `full` mode is implemented + type-checked but live-unverified this session (it would spend quota); first real use should be watched against the circuit breaker.
- BackgroundTasks die with the process; for runs that must survive a deploy/restart, move to a durable queue (the orphan-sweep currently marks such runs `failed` on restart).
- Phase C (React) consumes these endpoints: prospects table ← `GET /prospects` (filters/paging), run history ← `GET /runs`, "trigger run" ← `POST /runs` then poll `GET /runs/{id}`.

## ADR-015 — Frontend: the Prospects dashboard (React + Vite + Tailwind v4 + TanStack Query)

**Date:** 2026-06-30
**Status:** Accepted
**Context:** Phase C1 builds the first real screen of the product — a dense, professional Prospects table the outreach team works in daily, reading LIVE data from the Phase B API. The pipeline, DB, API, and Sheet write all stay untouched. The look is a "clean internal tool" (Linear/Retool — functional, dense, fast), not marketing-flashy.

### Decisions

1. **Stack: Vite + React + TypeScript + Tailwind v4 + TanStack Query, under top-level `frontend/`.** Vite for the dev server + build (fast HMR, first-class TS). **TanStack Query (v5) owns server state** — caching, request dedup, `keepPreviousData` so the table never flashes to empty while a page/filter loads, and a single place for loading/error status. **Tailwind v4** for styling: CSS-first config (`@import "tailwindcss"` + the `@tailwindcss/vite` plugin + `@theme` tokens) — no `tailwind.config.js`, no PostCSS. Versions confirmed current via context7 (not training data): vite 8.1, react 19.2, tailwindcss 4.3, @tanstack/react-query 5.10.
2. **A typed API client is the only seam to the backend.** `frontend/src/api/` holds TS interfaces that mirror the backend Pydantic models (`Prospect`/`PageOf<T>`/`Run`, the `TrustBand`/`SourceTag`/`GeoLevel` unions) and a thin `fetch` wrapper. The UI talks ONLY to the API — never to the DB or pipeline — so the layers stay cleanly separable and the contract is enforced end to end at compile time.
3. **Dev story: env-driven `VITE_API_URL` + the CORS already configured in Phase B (no proxy).** The Vite dev server runs on `:5173` (pinned, and in the backend's `CORS_ALLOW_ORIGINS`), the backend on `:8000`; the browser calls the API cross-origin and CORS allows it. Chosen over a Vite dev-proxy because Phase B already set CORS up — fewer moving parts. (Revisit a same-origin proxy if Phase D auth wants cookies.) Two-process dev flow documented in the README.
4. **Design direction: dense internal-tool aesthetic.** Refined zinc neutrals + a single indigo accent + Inter; 13px type with tabular numerals for aligned numbers; sticky header, frozen first column (Website) for scannability under horizontal scroll, hover highlight, subtle borders. Contact Trust as a colored badge (high=emerald / medium=amber / low=zinc), Source as MHD/AH badges, competitor links as a flagged red count, population right-aligned. Row click → a right slide-over drawer with the full prospect (provenance, competitor links, links out) — a drawer keeps table context, the right pattern for an internal tool. Loading (skeleton) / error / empty states all handled.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Plain `fetch` + `useState`/`useEffect` for data | yes | Re-implements caching, dedup, stale-while-revalidate, loading/error status by hand. TanStack Query is the standard for server state. |
| A heavy table lib (AG Grid / MUI DataTable) | no | Overkill + a generic look for one table; harder to hit the bespoke dense aesthetic. A hand-built table over the typed client is lighter and looks intentional. |
| Tailwind v3 (config-file + PostCSS) | no | v4 is current; CSS-first `@theme` + the Vite plugin is simpler (no config/PostCSS wiring). |
| Vite dev-proxy (`/api` → backend) | deferred | CORS is already configured in Phase B; a proxy adds config for no gain now. Reconsider for same-origin auth cookies in Phase D. |
| Modal dialog for row detail | no | A modal blocks the table; a slide-over keeps the list in view — better for an outreach workflow. |
| Server-driven pagination via cursor | no | The API already returns `total` + `limit`/`offset`; offset paging is simplest and matches it. |

### Live validation evidence (2026-06-30)

(See `docs/progress.md` Session 15.) With the backend (`uvicorn backend.app:app`, dev Postgres on `:5433`, 68 prospects) and the Vite dev server both running, verified in a real browser via Playwright: the shell connects (`/health` → "Backend connected"); the table renders the **68** real rows from Postgres via the API (real domains/emails — not mocked); **Trust=high → exactly 6** ("Showing 1–6 of 6", the 6 high-trust sites), **Source=AH → 23**; pagination pages 1–50 / 51–68 of 68; the row-detail drawer shows the full prospect incl. Contact Source provenance + the competitor link (`samhsa.gov`) listed; stopping the backend degrades gracefully ("Backend offline" + an error card with Retry, not a white screen). Backend suite stayed green (318); frontend `tsc` + build + oxlint clean.

### Trigger to revisit

- **Phase C2:** run-history view (`GET /runs`) + a "Run now" button (`POST /runs`) with run-status polling (`GET /runs/{id}` → running → done).
- **Phase D (auth):** protect the API; then a same-origin proxy / cookie story may beat `VITE_API_URL` + CORS.
- Deeper geo search (the API's `geo` filter is exact-match; a substring/typeahead would need backend support).
- A production build/serve story (the dashboard is dev-server only this phase).

## ADR-016 — Product identity (AuthorityScout), dark-first design system, and export

**Date:** 2026-06-30
**Status:** Accepted
**Context:** The C1 prospects table worked but read like a generic admin panel. Phase C1-Redesign makes it feel like a real SaaS product — identity, hierarchy, craft — and adds the export the user asked for. Data is already correct (68 real rows via the API); this upgrades PRESENTATION and adds EXPORT. The pipeline/DB/API auto-write all stay untouched; the UI still talks only to the API.

### Decisions

1. **Product identity: "AuthorityScout" + a radar logomark.** A named tool, not "MHD Authority Finder". A single-color SVG radar/scope mark (concentric rings, crosshair ticks, a sweep to a blip) in the app shell's top-left. The shell — slim left sidebar (logo, nav: Prospects / Runs·soon / Settings·soon, health, theme toggle) + topbar (page title, domain search, export actions) — is built to last: Phase C2 (Runs) and Phase D (auth/user menu) slot into it.
2. **Dark-first theming on a CSS-variable token system.** Dark is the default and the one made beautiful; light is a coherent toggle, persisted in `localStorage` with a no-flash `<head>` init. A confident **teal** brand (not default indigo). Tokens are semantic CSS variables (`--app/--surface/--raised/--border/--fg/--fg-muted/--fg-subtle/--brand` + trust/source/flag colors), defined per theme in `:root` / `.dark` and exposed to Tailwind v4 via `@theme inline` (utilities like `bg-surface`, `text-fg`, `text-brand`) + a `@custom-variant dark`. Everything themes through tokens — no hardcoded colors.
3. **Dashboard overview cards from a new `GET /stats`.** Five crafted cards (Total Prospects, High-Trust, % With Email, Geos Covered, Last Run) give the screen hierarchy and the data's state at a glance. A dedicated endpoint (one FILTER-aggregate query + the latest run) is cleaner than deriving client-side and scales past one page; tested against real Postgres.
4. **Table leveled up: client-side sort + column visibility.** Click any sortable header to sort the loaded page (trust/confidence by rank, population numeric, competitors by count, else locale); a Columns menu toggles visibility (Website stays frozen). Trust badges redesigned (pill + dot, emerald/amber/zinc, beautiful in both themes). Refined skeleton/empty/error states.
5. **Export: CSV client-side, Sheet via the backend — to a NEW TAB, master untouched.** "Export CSV" pages through all matching rows (the API caps `limit` at 200) and downloads the deliverable columns client-side. "Export to Google Sheet" → `POST /export/sheet` on the active filters. **A plain service account cannot create standalone spreadsheets (Drive 403),** so the export adds a uniquely-named **new tab** to a workbook the SA can already edit (`EXPORT_SHEET_ID`, default the master) and returns its `#gid` URL — the auto-write tab (`Sheet1`) is never touched. A success toast links to the new tab. The endpoint mocks Google in tests (asserting the filtered rows reach the exporter + the addSheet/write calls); verified live once.
6. **Richer, actionable detail drawer.** A trust panel explaining WHY a contact is trusted (band + provenance + page confidence), contact fields with copy-to-clipboard + mailto/tel buttons, a prominent resource-page link + org description, competitor chips — a considered layout, not flat label/value rows.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Keep the admin-panel look | no | The brief is a real product; identity + craft were the point of the phase. |
| `prefers-color-scheme` only | no | The user wants an explicit, persisted dark-first choice with a toggle. |
| Default indigo brand | no | Asked for a brand with a point of view; teal commits to one. |
| Derive stats client-side from /prospects + /runs | no | Needs all rows loaded; a `GET /stats` aggregate is cleaner + scales. Endpoint tested. |
| Export = create a fresh standalone spreadsheet | **blocked** | A plain service account has no Drive storage → `spreadsheets.create` returns 403. New tab in an editable workbook is the working surface ("or new tab" was allowed). |
| Export tabs in the master workbook by default | acceptable fallback | Works now (Sheet1 untouched); `EXPORT_SHEET_ID` points exports at a dedicated workbook to keep the master clean. |
| A heavy table/grid lib | no | A hand-built sortable table over the typed client hits the bespoke dense aesthetic; lighter. |

### Live validation evidence (2026-06-30)

(See `docs/progress.md` Session 16.) Dark theme reads as a designed product; the light toggle is coherent and persists. Stat cards show real numbers (Total **68**, High-Trust **6**, With Email **74%** = 50/68, Geos **5**, Last Run success). Table renders the 68 real rows; sort by Population asc puts Newport Beach (83,845) first; the Columns menu hides Phone; **Trust=high → 6** through the redesigned UI (filters intact). **CSV** downloaded all 68 rows with the deliverable columns. **Sheet export** (curl + UI) created a new tab with the filtered rows and returned a `#gid` URL — and the master **Sheet1 stayed 69 rows (untouched)**; the proof tabs were then deleted, leaving the master pristine. Drawer is actionable (copy + mailto/tel, trust rationale, competitor chips). 324 backend tests green (318 + 6 stats/export); frontend tsc + build + oxlint clean; the CLI + master auto-write are unchanged.

### Trigger to revisit

- **`EXPORT_SHEET_ID`:** set a dedicated export workbook (shared with the SA) in production to keep exports out of the master file entirely.
- **Phase C2:** wire the Runs nav item — run history (`GET /runs`) + a "Run now" trigger (`POST /runs`) + status polling — into this shell.
- **Phase D (auth):** the sidebar/topbar reserve space for a user menu; protect the API + the export/trigger endpoints.
- Domain search is client-side over the loaded page; a server-side substring search would need API support.

## ADR-017 — Runs screen: history, "Run now" trigger, live status polling

**Date:** 2026-07-01
**Status:** Accepted
**Context:** Phase C2 — the last UI screen. The backend (ADR-014) already exposes `GET /runs`, `GET /runs/{id}`, and `POST /runs` (a cost-safe background job that respects the S11 caps). This builds the frontend Runs view + a "Run now" trigger + live status polling, into the "Runs" nav slot the C1-redesign shell (ADR-016) reserved. Engine/DB/API/Sheet/dashboard stay untouched; the UI talks only to the API. With this, the UI is complete (prospects + runs + trigger).

### Decisions

1. **View switching in the shell (no router).** The Sidebar nav is now clickable; App holds a `view` state and renders `ProspectsScreen` or `RunsScreen`. The prospects UI was extracted from `App` into `ProspectsScreen`; App is now the shell + view switch + shared toast. A full router is overkill for two screens (+ Settings·soon); this keeps the shell the single composition point Phase D (auth/user menu) slots into.
2. **Runs list = the same table craft as prospects.** `RunsScreen` renders `GET /runs` (newest first) as a dense, themed table: Site tag, a **RunStatusBadge** (running = amber + spinner, success = emerald, failed = rose — matching the trust-badge treatment), relative timestamps (`timeAgo`), duration, geos/rows/billed, and the error summary in a Notes column. Loading skeleton / empty ("no runs yet — start one") / error states, all designed. Billed>0 is tinted amber (cost signal); billed=0 reads as the safe default.
3. **"Run now" surfaces the cost-safety.** A popover picks site (MHD/AH/Both) and mode: **"New geos only" is the default**, labelled "Cost-safe — spends nothing if nothing is new" (the S11 incremental path); **"Full re-scan" is clearly warned** ("re-scans every known geo — may use search credits"). Confirm → `POST /runs` (via a TanStack mutation) → 202 + run_id → a "Run started" toast; never blocks the UI. The S11 caps are enforced backend-side; the UI makes the safe path the obvious one.
4. **Live status polling via `refetchInterval` as a function.** `useRuns` sets `refetchInterval: (query) => query.state.data?.items.some(r => r.status === 'running') ? 2000 : false` — polls every 2s while any run is running, stops once all are terminal (the current TanStack Query v5 idiom, confirmed via context7). The triggered run appears (the mutation invalidates `['runs']`), then the list flips running → success/failed live, no refresh.
5. **Post-run refresh via cache invalidation.** `RunsScreen` tracks running run ids across polls; when a previously-running run turns terminal it invalidates `['prospects']` + `['stats']`, so the dashboard's rows + Last Run card update automatically (TanStack Query invalidation, per context7). A successful run with new prospects surfaces them without a manual refresh.

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Add a client router (react-router) | no | Two screens + a soon-tab; view state in App is simpler and the shell stays the one composition point. |
| Poll `GET /runs/{id}` per running run | considered | Polling the list (one query) updates the whole table live and is simpler; the list already carries every run's status. |
| `setInterval` + manual refetch | no | `refetchInterval`-as-a-function is the built-in idiom — self-stopping, no leak, pauses when the tab is hidden. |
| Block the UI / spinner overlay on trigger | no | 202 + a toast + a live-updating row is the right non-blocking UX; the user keeps working. |
| Hide the full-run option | no | Power users may want it; surfacing it *with a credit warning* (and defaulting to cost-safe) is more honest than hiding it. |

### Live validation evidence (2026-07-01)

(See `docs/progress.md` Session 17.) Runs page rendered the 3 real runs from Postgres (the S14 no-op + two S13 runs) with correct details, themed in **dark and light**. "Run now" → Both, incremental → a "Run started" toast + a new run row; polling flipped it running → **success** without a manual refresh (the total went 3 → 6 across triggers, each resolving live). Every triggered run was the **cost-safe no-op** — `billed=0`, `rows=0`, `geos=0` — shown correctly (Billed —, Rows 0), proving the safe path is visible to the user (0 new geos confirmed by a free sitemap diff first; no quota spent). After the runs, the Prospects **Last Run** card updated to "Jul 1, 2026" (stats invalidation fired), Total stayed 68 (no-ops add nothing). 324 backend tests green; frontend tsc + build + oxlint clean; the API/CLI/master Sheet are unchanged. (The no-op completes in ~5s — faster than a screenshot round-trip — so the transient running spinner wasn't freeze-framed, but the live count increment + auto-resolution prove the polling.)

### Trigger to revisit

- **UI COMPLETE** (prospects + runs + trigger). Remaining: **Phase D** (auth over the stack — the shell reserves the user-menu/Settings slots) and **Phase E** (hosting/deploy).
- A run detail view (`GET /runs/{id}`) could show the full funnel; the list currently carries the headline counts.
- For a real (non-no-op) run, the running spinner + a longer duration would be visible; the no-op is intentionally instant.

## ADR-018 — Authentication: Google sign-in, server-side verify, email allowlist, app session

**Date:** 2026-07-03
**Status:** Accepted
**Context:** Phase D makes the app private. It's a single-org internal tool (District Behavioral Health), so a handful of trusted people need in and no one else. We want zero password management and no user-admin UI. Google sign-in + a hard-coded email allowlist fits: the team already has Google accounts; access is a config value, not a database. The pipeline/CLI/scheduler are separate headless entry points that never touch the HTTP API and must keep working without login.

### Decisions

1. **Google sign-in, verified SERVER-SIDE.** The frontend renders `@react-oauth/google`'s `<GoogleLogin>`, which returns a Google ID token (`credential`). The backend verifies it with `google-auth` (`id_token.verify_oauth2_token`, audience = our client id) — never trusting a client-side decode. We additionally enforce a trusted issuer and `email_verified`. Both failure classes (`ValueError` and `GoogleAuthError`) map to 401.
2. **Email allowlist over user management.** For one org, a database of users + roles is overkill. `ALLOWED_EMAILS` (a comma-separated env value, parsed to a lowercased list) is the entire authorization model: a verified email not on the list gets **403** with a clear "This account isn't authorized — contact your admin." message. Adding a teammate is an env change, not a migration.
3. **App session = a signed JWT in an httpOnly cookie (not Google's token).** After verify + allowlist, the backend mints its OWN HS256 JWT (`JWT_SECRET`, 12h) and sets it as an httpOnly, `SameSite=Lax` cookie — the app's session, decoupled from Google. `SameSite=Lax` is correct for dev because `localhost:5173` ↔ `localhost:8000` is **same-site** (port isn't part of a site), so the cookie flows; `Secure` is off for localhost-http and flips on for prod-https (`AUTH_COOKIE_SECURE`). The frontend sends `credentials:'include'`; CORS keeps `allow_credentials=True` with explicit origins (never `*`).
4. **Guard the data routers, keep two routes public.** `stats`/`prospects`/`runs`/`export` are included with `dependencies=[Depends(get_current_user)]` — no session ⇒ 401. `/health` and `POST /auth/google` stay public; `GET /auth/me` requires a session (it's how the SPA learns whether it's logged in). The frontend gates the whole app on `/auth/me`, shows an on-brand login screen otherwise, and a global 401 handler flips back to login on session loss.
5. **The pipeline/CLI/scheduler are untouched.** Auth lives entirely in `backend/`; `run`/`schedule` import the pipeline, not the API, so headless runs never hit a login. Verified: 338 tests green, CLI + scheduler load, the master Sheet auto-write is unchanged.
6. **Google project in Testing mode with explicit test users** is the intended private setup (no public-app verification needed for a handful of users). Prod adds the deployed origin to the OAuth client's Authorized JavaScript origins (Phase E).

### Alternatives considered

| Choice | Considered | Why not |
|---|---|---|
| Passwords + a users table | no | Password storage/reset + a user-admin UI for a 2–3 person org is overkill and a liability. Google sign-in has none of that. |
| Verify the Google token client-side | no | A client-side JWT decode is unverified — trivially forgeable. Verification MUST be server-side against Google's keys. |
| Keep using Google's ID token as the session | no | It expires in ~1h and re-verifying every request adds a Google dependency per call. Mint our own short session instead. |
| JWT in `localStorage` + `Authorization` header | no | XSS-readable. An httpOnly cookie can't be read by JS; `SameSite=Lax` covers CSRF here. (A Bearer fallback exists for non-browser clients.) |
| `SameSite=None; Secure` cookie | no | Requires HTTPS; breaks on localhost-http. Lax works because the two dev origins are same-site. |
| A real user database + roles | deferred | Not needed for one org. If multi-tenant/roles ever arrive, revisit — the allowlist is the seam. |

### Live validation evidence (2026-07-03)

(See `docs/progress.md` Session 18.) **Live-browser:** unauthenticated → the on-brand login screen (logo + "Sign in with Google"); with a valid session the full dashboard loads, the sidebar shows the signed-in user (name + email + avatar), features work (Trust=high→6, Source=AH→23, runs), and logout clears the cookie and returns to the login screen. **Backend-verified (curl + tests):** `/prospects`,`/stats`,`/runs`,`/auth/me` all 401 unauthenticated; a bad Google token → 401; a validly-verified-but-not-allowlisted email → **403** (test, with a mocked verified token — Step 6.4); a minted session → `/auth/me` 200 + `/prospects` 200. **NOT live-browser:** the real Google popup can't complete headless, so the logged-in state was verified by injecting a real backend-minted session (a legitimate app session, standing in for a completed Google login) — the Google *verification* path is covered by the backend tests, not fabricated. 14 auth tests; 338 backend total; frontend tsc/build/oxlint clean; CLI + scheduler + master Sheet unchanged. Two bugs were caught in live verification and fixed: a 401 self-loop on `/auth/me`, and the logout gate (TanStack Query retains data on error → also gate on `isError`).

### Trigger to revisit

- **Phase E (hosting):** deploy the stack; add the production URL to the OAuth client's Authorized JavaScript origins; set env on the host (`ALLOWED_EMAILS`, `JWT_SECRET`, OAuth creds, `AUTH_COOKIE_SECURE=true`, prod `CORS_ALLOW_ORIGINS`/`VITE_API_URL`). If frontend + API share an origin in prod, the cookie is simply same-origin.
- `ALLOWED_EMAILS` in `.env` currently lists one `districtbehavioralhealth.com` address — add each teammate (and `meetashirr@gmail.com` if that account should sign in) there and as an OAuth test user.
- If the app ever needs roles or >~10 users, replace the allowlist with a users table.

## ADR-019 — Phase F1: scale-test at real volume, cost-capped, then fix the precision defects it surfaced

**Date:** 2026-07-06
**Status:** Accepted
**Context:** The pipeline had only ever run over 5 cached geos. Before a full outreach push we needed to know how it behaves on *unseen* geos at real volume — without spending the shared SerpAPI budget. Hard rule: **≤40 billed searches for the whole session**, count every billed call, report the free live-geo count before spending.

### Decisions

1. **Free reconnaissance before any spend.** The geo monitor reads both live sitemaps for $0: **72 live geo pages** (MHD 23 — 2 state / 4 county / 17 city; AH 49 — all state), **8 already cached** (free to re-run), **64 new**. Projected full-run cost of everything new ≈ **253 billed searches** (~$3.80 at SerpAPI's rate). Reported before spending a cent. Structural finding: **AH publishes only state-level geos** — county/city depth is MHD-only, so unseen county/city coverage must come from MHD.
2. **A controlled, capped sample — not the bare `run` CLI.** `run` loads *all* known geos; a scale test needs an explicit target list under the cap. An 8-geo, level- and site-mixed sample (3 AH state incl. rural Wyoming, 2 MHD county, 3 MHD city incl. the S12 fuzzy-match trap Palos Verdes) projected to **30 billed**. Enforced with `SerpApiClient(max_billed=38)` — a hard backstop below 40; discovery concurrency is 2 with sequential per-geo queries, so worst-case overshoot at the cap is ≤1. **Actual first run: 29 billed** (Wyoming's `site:.gov` substance-abuse query returned zero results that hour).
3. **Adversarial multi-agent analysis, then fix only what was confirmed.** The run completed cleanly — **no crashes, no whole-geo failures, cost fully accounted, DB idempotency flawless, population exact and honest** (74/87, all correct ACS; Palos Verdes `not_found` is right). A parallel dimension analysis + adversarial verification confirmed **6 data-precision defects** (out of more candidates — expected 403/DNS/robots noise was correctly rejected as external, not bugs). Each fixed via TDD, one atomic commit:
   - **Reject emails with interior whitespace** (HIGH). A malformed mailto `counseling _center@pba.edu` was published at HIGH trust and out-ranked the valid same-domain dept inbox. Mailto bypasses the body regex, so `_is_junk_email` gained a whitespace guard.
   - **Reject glued-label junk emails.** lxml `text_content()` glued a phone tail + doubled `Email` labels onto an inbox (`5000EmailEmailcarecoordination@…`); the `\d{5,}` guard missed the 4-digit prefix. Added a leading-4-digit / doubled-label guard.
   - **Exclude national federal portals as candidates.** `govinfo.gov` and `data.gov` (geo-less national portals) were published as per-geo authorities; added them + peers (gpo/congress/regulations/federalregister) to `FEDERAL_DOMAINS`.
   - **Scope the crawl fallback to the per-agency dedupe key.** The crawl used the coarse registrable domain (`ny.gov`), so a `dol.ny.gov` candidate whose page 403'd hopped into a sibling agency `omh.ny.gov` and recorded its homepage under the DOL row. Switched the crawl + redirect-shell guard to `dedupe_key`.
   - **Wrap transport errors so the crawl fallback runs.** A raw `httpx.TransportError` (DNS/timeout) escaped `fetch()` unwrapped, so the detector's `except FetchError` missed it and the whole candidate aborted instead of falling back. Wrapped it as `FetchFailedError`.
   - **Treat an empty SerpAPI result as valid, not an error.** SerpAPI returns HTTP 200 + `{"error":"…hasn't returned any results…"}` for a genuinely empty `site:.gov` search (rural geos); the client raised it as a hard error, miscounting it as a query failure and never caching it (so it re-issued live every run). Now returned empty (unbilled — SerpAPI doesn't bill no-results — but cached).
4. **Deferred, NOT fixed: the wrong-state candidate risk.** ~9% of rows were out-of-geo candidates whose root cause is that the scorer's wrong-state reject is *text-only* and never validates the candidate domain's real location. This was **not** adversarially confirmed as a discrete defect and the fix is a larger change (domain geolocation), so it is deliberately excluded — but flagged as the single biggest quality risk at 64-geo scale (24 of those are state-level AH runs, the exact trigger) and recommended for a spot-check before/during the full run.

### Verification evidence (2026-07-06)

Cached re-run of the same 8 geos after the fixes (**billed = 1** — 29 cache hits + the one previously-uncached Wyoming query, which this hour returned real results and is now cached; **session total 30 of 40**). Every defect fixed on real data: **0** `govinfo.gov`/`data.gov` rows; `pba.edu` now publishes `counseling_wellness@pba.edu` (the valid inbox); `oc.gov` now `carecoordination@ceo.oc.gov`; `dol.ny.gov` now points to `dol.ny.gov/about-us`, not `omh.ny.gov/`; Wyoming `errors=0`, `query_failed=0`; **0 junk emails** in the Email column. Corrected funnel: 83 rows, 44 with email (53%), 73 with phone (88%), population 70/83 (84%). **344 tests pass** (338 + 6 new), pyright 0, ruff clean; CLI + scheduler load; master Sheet untouched; dev DB restored to its canonical 68/6/5 baseline (the pre-fix scale rows were throwaway test data on unseen geos).

### Verdict

Infrastructure **scales safely** (cost-bounded, idempotent, honest, per-geo isolated). With the 6 precision fixes landed, the pipeline is ready for a full **64-geo run at ≈253 billed searches (~$3.80)** — subject to a spot-check of the deferred wrong-state risk on the state-level AH geos.

### Trigger to revisit

- Before the full 64-geo push: spot-check wrong-state/out-of-geo candidates on the AH state geos; if material, add candidate-domain geolocation validation to the scorer.
- Expected external noise scales ~linearly (~23% of candidates 403/DNS/robots) — non-fatal, per-candidate isolated.

## ADR-020 — Wrong-state validation: domain geography beats page text

**Date:** 2026-07-06
**Status:** Accepted
**Context:** Session 19 (ADR-019) flagged ~9% of scale-test rows as wrong-state / out-of-geo — the top
quality risk for the full 64-geo run (24 of those are state-level AH geos, the exact trigger). The scorer's
wrong-state check was **text-only**: it rejected a page only when *another* state's name dominated the text
and the target was absent. It never inspected the candidate **domain's** real location. A wrong-state row is
not "low quality" — it is **wrong** (it would email a different region's org), the same class as the
redirect-shell / off-domain defects already killed. The audit is `docs/wrong-state-audit.md`.

### Decisions

1. **The candidate domain's geography is authoritative, where reliably derivable.** New
   `page_detector/geography.py::candidate_state(url)` derives a `.gov`/`.us` domain's state slug ONLY from
   reliable signals: a state-portal registrable domain/subdomain (`dol.ny.gov` → NY; `hhs.texas.gov` → TX)
   and a `county{2-letter-abbr}` suffix (`wyomingcounty**ny**.gov` → NY — a county domain always encodes its
   own state, and the "county" anchor makes the abbr safe). Everything ambiguous returns `None`.
2. **Domain contradiction → hard reject** (`wrong_state`), regardless of page text. This is the essential
   catch: `wyomingcountyny.gov` is Wyoming *County, New York*, and its page is full of the word "Wyoming"
   (the county's name), so the text check not only passed it but *awarded the target-state bonus*. Only the
   domain reveals the truth. Domain-confirmed candidates additionally **suppress** the text-based reject (a
   confirmed-California agency is a California org even if its page discusses another state).
3. **Geo-confirmation gate → demote, not delete, the unconfirmable.** A candidate is *geo-confirmed* iff the
   domain confirms the target state, OR the target state is present **and not out-mentioned** by another
   state in the text (a national/multi-state page naming the target once is weak evidence), OR (county/city)
   the locality name appears. A candidate confirmed by none of these is capped to **low** confidence and
   flagged with a `geo_unconfirmed` signal — never silently shipped as verified.
4. **Precision over recall — and only assert what's genuinely derivable.** Hard-rejection requires domain
   proof; everything unconfirmable is demoted (flagged for a human), never wrongly killed. Deliberately NOT
   derived, because they misfire: bare `{city}{abbr}.gov` (`napa.gov` ends in `pa` = Pennsylvania but is
   California), full-state-name suffix (`portwashington.gov` is NY/WI, not Washington state), any `.edu`,
   cryptic acronyms (`dconc.gov` = Durham County NC). These fall back to the text/locality gate honestly.

### Honest limits

- **`.edu` universities carry no state in the domain.** An out-of-state university whose page *incidentally*
  names the target state or a nearby big city can still pass the text gate at reduced confidence (live: CU
  Anschutz `cuanschutz.edu`, Colorado, stayed **medium** for a Palos Verdes geo because its page mentions
  Los Angeles / California). Hard-rejecting these would need a university→state dataset (out of scope) and
  would risk false-rejecting legitimate in-state schools — so they are left demoted/flagged, not deleted.
- **False positives are demotions, never rejections.** A correct in-state candidate whose page does not
  strongly name its state (live: `plano.gov`, a Texas city, medium→low) is demoted to a flagged low, not
  removed. That is the accepted precision-over-recall cost.

### Live validation (2026-07-06, billed 0 — cached)

Re-ran detection over the 8 S19 cached geos. `wyomingcountyny.gov` → **hard-rejected** (`detect.wrong_state
dominant=new-york`); `divinemercy.edu` (Virginia), previously **high** for Wyoming → **low**; the other
out-of-state `.edu` cases already low, unchanged. Residual: `cuanschutz.edu` still medium (incidental-text
limit above). **7 of 8 wrong-state cases now rejected-or-low** (the worst, actively-misleading high-confidence
case eliminated). The 5-geo known-good baseline was re-checked (billed 0): **contact-trust high still 6 and
medium still 18 — no legitimate row lost or demoted** (low-trust dropped 44→42), and the gate additionally
rejected two genuine wrong-state candidates for the Orange County *California* geo — `orangecountync.gov`
(North Carolina) and `orangecountyva.gov` (Virginia) — both high-*confidence*, exactly the dangerous
"looks verified but wrong region" class. New tests: 12 geography unit + parametrized S19 regressions, 5
scorer-gate tests.

### Trigger to revisit

- If out-of-state `.edu` slips prove material at full scale, add a university→state reference dataset (then
  `.edu` domains become derivable and their contradictions hard-rejectable).

## ADR-021 — Full production run: the real dataset (72 geos → 622 prospects)

**Date:** 2026-07-06
**Status:** Accepted
**Context:** With the pipeline scale-tested (ADR-019) and wrong-state-hardened (ADR-020), this is the real
build: run the FULL live geo corpus to create the client's production dataset in Postgres + the master
Google Sheet. A deliberate, approved, one-time SerpAPI spend, capped so a bug couldn't overspend.

### What ran

Free pre-flight recon (billed 0): 72 live geos (MHD 23, AH 49), 56 new-billable, projected **223** — below
the ~253 S19 estimate (the 8 S19 sample geos were already cached). Ran the full pipeline over all 72 geos
with `SerpApiClient(max_billed=320)` (hard backstop), per-geo isolation on.

### Results

- **Cost: 223 billed** — exactly the projection, well under the 320 cap (~$3.35).
- Funnel: 72 geos → **1,754 candidates → 637 detected → 622 unique prospects** (deduped by website+geo),
  5,114 fetches (3,320 httpx / 533 Playwright). **0 whole-geo failures** — per-geo isolation held across all 72.
- Quality (622 rows): contact-trust **high 77 / medium 146 / low 399**; confidence high 298 / med 179 / low
  145; **email 62% (386), phone 90% (562), population 88% (548)**; 82 rows link a competitor; source AH 393 /
  MHD 229.
- **Wrong-state gate (ADR-020) fired 21 times on real data** — 21 out-of-state candidates hard-rejected that
  the old text-only check would have shipped. Rejections: 497 (incl. the 21 wrong_state); 632 fetch-failed
  (expected external WAF/DNS/robots noise, ~36% of candidates — non-fatal, isolated).
- **Playwright spot-check (8 rows, mixed sites/levels/trust): 8/8 geo-correct.** The 3 high-trust rows are
  real university counseling centers with same-domain dept emails (cmich.edu MI, louisiana.edu LA, une.edu
  ME); bergencountynj.gov is a textbook county behavioral-health page; uwyo.edu is the *legit* Wyoming
  counseling center the wrong-state gate correctly KEPT. Weak picks were honestly ranked down: scuhs.edu (right
  org/CA but a news-archive page, medium), edd.ca.gov (CA labor-market, off-topic, correctly low).
- Idempotency: re-writing appended **0** to the Sheet and left the DB at 622.

### Incident + recovery (honest)

The run took ~2 hours (detection-bound); partway through, the **Docker daemon stopped** (host sleep), so
Postgres was gone when the pipeline finished and tried to write. The DB write is a single delete-then-persist
transaction that only commits at the end, so it **never committed** (DB safe at its baseline), and the Sheet
write is sequenced after it, so it **never ran** (Sheet untouched). The pipeline had already written a **CSV
backup** of all rows. Recovery: restart Docker/Postgres, then a `finalize` script re-wrote the 622 already-
computed rows from the CSV to Postgres + the Sheet with **zero re-spend**. Two things saved it: the atomic DB
transaction (no partial/corrupt write) and the CSV-first backup. **Lesson:** for multi-hour runs, either keep
the host awake or persist incrementally; the CSV backup is the safety net either way.

### Verdict

The production dataset is **demo-ready**: 622 real, geo-correct, quality-ranked prospects across all 72 geos,
live in Postgres (the SaaS app) and the master Sheet (outreach). Remaining hardening is operational, not
correctness: frontend tests, run monitoring/alerting, and outreach-status tracking on top of the dataset.

### Trigger to revisit

- Re-run periodically (the scheduler already does new-geos-only, cost-safe) as MHD/AH add geo pages.
- The weak-page picks (news archives, licensing boards) are the next precision target if the client wants
  higher medium-tier quality.

## ADR-022 — Outreach status tracking: user-owned data alongside pipeline-owned data

**Date:** 2026-07-07
**Status:** Accepted
**Context:** The dataset is complete (622 prospects) but AuthorityScout could only *find* prospects, not
track what the team *does* with them. Phase F3 adds outreach tracking — mark a prospect
contacted/responded/interested/etc. + notes — turning the app into a workflow tool. Touches DB → API → UI.
0 billed (pure feature work on existing data).

### The make-or-break constraint

Outreach status is **user-entered** data living in the same `prospects` row as **pipeline-generated**
discovery data. When the pipeline re-runs and upserts a prospect, it must **not** overwrite the team's
status/notes. Get this wrong and a re-run erases their work. So: the pipeline owns the discovery fields
(website, page, email, trust, …); the user owns the outreach fields; the upsert preserves user fields.

### Decisions

1. **Separate ownership on one row, preserved by the upsert's shape.** New user-owned columns:
   `outreach_status` (enum, default `not_contacted`), `outreach_notes`, `contacted_at`,
   `outreach_updated_at`, `outreach_updated_by`. The pipeline's `upsert_prospect` lists ONLY discovery
   fields in both its INSERT `.values()` and its `on_conflict_do_update(set_=…)`. Because the outreach
   columns are absent from both, a re-run **can't** touch them: a brand-new prospect gets the column
   defaults; an existing one keeps exactly what the team entered. The preservation is structural, not a
   special case — and it's pinned by a real-Postgres test (mark contacted+notes → re-upsert with fresh
   discovery data → assert discovery updated AND status/notes survived).
2. **Status set = the outreach funnel.** `not_contacted` (default) / `contacted` / `responded` /
   `interested` / `not_interested` / `linked` (they published the backlink — the goal) / `bounced`.
   `contacted_at` is stamped the first time a prospect leaves `not_contacted`.
3. **`PATCH /prospects/{id}/outreach`** (auth-required) writes via a dedicated `update_outreach_status`
   repository method and records the signed-in user's email as `outreach_updated_by` — the API never
   trusts the client for who-did-it. `GET /prospects` gains an `outreach_status` filter; `GET /stats`
   gains a per-status breakdown for the dashboard.
4. **UI: status is first-class + editable.** A colored status pill column (sortable by the funnel order) +
   a status filter; the detail drawer has an editable dropdown + notes + save (→ PATCH, optimistic pill +
   toast, shows who/when); a dashboard card ("N worked · M responded · K to go"). Matches the existing
   design tokens (pills reuse the `.badge` system).
5. **The Sheet stays discovery-only.** The master auto-write and the on-demand export are NOT extended with
   outreach columns: the DB (via the app) is the outreach source-of-truth, and folding user data into the
   pipeline's `OutputRow` would blur the exact ownership boundary this feature depends on. `OutputRow` is
   untouched, so the master write is byte-identical. (Future option: export could append outreach columns
   read from the DB.)

### Bug caught in live verification

The PATCH persisted correctly but first returned **500**: `updated_at` has `onupdate=func.now()`, so after
the UPDATE its value is server-computed + expired, and the sync `ProspectOut.model_validate(row)` attempted
an async-illegal lazy refresh (`MissingGreenlet`). Fixed by `await session.refresh(row)` after commit before
serializing. (The API tests assert the response body, so CI would have caught it; live verification caught it
first.)

### Verification (0 billed)

Migration: all **622** rows default to `not_contacted`, discovery data 100% intact. Live (real 622-row DB,
minted session): drawer status change → persists, pill flips to Contacted, dashboard card updates live to
"1 · 621 to go", `outreach_updated_by` = the signed-in user; filter by status works; unauthorized PATCH →
**401**. **Make-or-break proven twice** — at the repository level and end-to-end through the pipeline's actual
`upsert_prospect` write path on a real production prospect (status + notes survived, discovery updated).
**381 tests** (370 + 11 outreach), pyright 0, ruff clean; CLI/scheduler + master Sheet write unchanged;
frontend builds + lints clean. Dataset left pristine (622/622 `not_contacted`).

### Trigger to revisit

- If the team wants outreach in the exported sheet, add DB-sourced outreach columns to the on-demand export
  (never to the master auto-write).
- If >1 person edits concurrently, add optimistic-concurrency (the `outreach_updated_at` is the seam).

## ADR-023 — Frontend tests + error monitoring (production-readiness)

**Date:** 2026-07-16
**Status:** Accepted
**Context:** Final hardening before hosting (Phase E). Two gaps: the React app had ZERO tests (the backend
had 381), and a production failure alerted no one — the S21 "laptop died mid-run" class of incident would
pass silently. This session closes both. No features, no visual change, 0 billed, the 622-prospect dataset
untouched.

### Part A — frontend tests

1. **Vitest + React Testing Library + MSW, testing BEHAVIOR not coverage.** Vitest (jsdom, globals) wired
   into the Vite config; MSW v2 intercepts the API at the network layer so tests exercise the real client +
   hooks + component logic against realistic response shapes — not stubbed hooks. Every test asserts a
   behavior a user would notice; no snapshot-only or `expect(true)` filler. **30 tests** protect: the API
   client (filter/pagination params on the wire, parsing, `ApiError` on non-2xx, PATCH/POST bodies); the
   **auth gate** (401→login, authed→app, logout→login) and **login 403** ("isn't authorized" message, not a
   crash); the **prospects table** (rows, trust sort asc/desc, column hide, row select); **filters** (trust
   filter hits the API + renders only the subset; empty + error states); the **detail drawer + outreach**
   (contact/competitor chips, clipboard copy, an outreach change PATCHes the right body + flips the pill +
   toasts success, and an error path toasts failure); **runs + Run-now** (rows, POST with the chosen
   site+mode, error toast); and the **ErrorBoundary** (a crashing child shows the recovery screen).
2. **Deliberately NOT tested:** pure-visual styling (the elevation/theme tokens), exact pixel layout, and
   the real Google GSI iframe (stubbed — its 403/success handling IS tested; the sign-in *transport* is
   Google's). Coverage % is not chased; specific product-breaking behaviors are protected.

### Part B — error monitoring (Sentry, DSN-gated)

3. **Sentry, enabled only by a DSN — silent in dev.** Backend `SENTRY_DSN` / frontend `VITE_SENTRY_DSN`
   BLANK ⇒ `init` never runs and every `capture_*` is a no-op, so local dev + tests are silent and CI sends
   nothing. Real DSNs are a hosting-time step.
4. **Backend: capture unhandled exceptions AND background-run failures.** The shared core
   (`authority_finder/monitoring.py`) inits Sentry; the FastAPI wrapper (`backend/monitoring.py`) adds the
   Starlette + FastAPI integrations for request context. CRITICALLY, the two places a run can die with no
   request wrapping it are captured explicitly: the API background task (`execute_run`) and the standalone
   scheduler's per-site failure (`run_tick`) — the 3am scheduled-run case. The scheduler CLI inits Sentry
   itself so the Docker cron reports too.
5. **Frontend: an ErrorBoundary + graceful fallback.** `@sentry/react` `Sentry.ErrorBoundary` wraps the app
   with an on-brand recovery screen (reload button) instead of a white page, and reports the crash. Errors
   only — no tracing, no session replay (free-tier friendly and replay-free avoids shipping PII-heavy DOM).
6. **Scrubbing policy — never send secrets, redact PII.** `send_default_pii=False` (the SDK default) already
   denies authorization/cookie/session/token/secret/api_key from event payloads and request headers; a
   `before_send` (both stacks) additionally drops the request cookies + body outright, scrubs sensitive
   headers, and redacts email addresses (prospect PII) from exception messages. So the Google session, JWT,
   `.env` secrets, and prospect emails never leave the process.

### Verification (0 billed)

Frontend **30 tests** (9 files) green; build + oxlint clean. Backend **387 tests** (381 + 6 monitoring) —
the monitoring tests prove: `scrub_event` strips cookies/body/headers + redacts emails; `init_sentry` returns
False (never touches Sentry) with no DSN and True with one; and `execute_run` calls `capture_exception` when
a background job raises (the 3am case, no real event sent). The ErrorBoundary fallback is proven by a
crashing-child test. Nothing broke: db+api tests pass with the monitoring-wired app, CLI/scheduler + master
Sheet unchanged, the 622-prospect dataset untouched (622/622 not_contacted).

### Hosting-time (what the user must do — Phase E)

Create two Sentry projects (a Python/FastAPI one and a React one); set `SENTRY_DSN` + `SENTRY_ENVIRONMENT`
in the API/scheduler env and `VITE_SENTRY_DSN` in the frontend build env. Nothing else — monitoring turns on
the moment a DSN is present.

### Trigger to revisit

- If error volume approaches the free tier, add sampling (`sample_rate`) or upgrade.
- If a specific user flow needs regression protection, add a behavior test (the MSW harness makes it cheap).

## ADR-024 — Sheet data quality: geolocation gates, trust-first sort, junk detection

**Date:** 2026-07-18
**Status:** Accepted
**Context:** The live production deliverable (622 rows / 72 geos, ADR-021) was audited before the client
digs in. Real defects reached the sheet: universities filed under the wrong state, phones belonging to a
different state's org, press releases scored high, whole states missing population, and 77 high-trust rows
scattered across an alphabetical sheet. Diagnosis first (`docs/sheet-quality-audit.md`), then evidence-driven
fixes. **0 billed** — everything runs off the cached corpus + the persisted rows.

### Decisions

1. **Diagnose before fixing; fix by volume/severity.** Every defective row was bucketed with counts + named
   examples across the full 622 BEFORE any code changed: A `.edu` wrong-state (31), B phone area-code
   contradiction (38), C junk page promoted (12 high/medium), D third-party contact (61 — already low, not a
   defect), E population blank (74; 50 fixable), F federal leak (irs.gov ×2). Scope followed the evidence.

2. **Phone area-code geography via `phonenumbers`, not a hand-kept table (bucket B).** Phones encode
   geography (NANP). We resolve a number's state through the maintained `phonenumbers` geocoder
   (libphonenumber's data — authoritative, already a dependency) rather than hand-typing ~300 area codes —
   a deliberate deviation from "build an area-code table" because the library IS the reliable current source
   and is far less error-prone. A phone whose area code contradicts the geo's state is dropped (precision
   over recall: only on a *confirmed* contradiction; toll-free carries no geography → neutral, kept).

3. **`.edu` → state from the College Scorecard, closing the ADR-020 gap (bucket A).** ADR-020 geolocated
   `.gov`/`.us` but deferred `.edu` (a bare `.edu` label carries no state). We vendor a snapshot of the
   federal College Scorecard institution directory (`data/university_states.csv`, domain → state slugs, 90%
   corpus coverage) and hard-reject a `.edu` whose geo is in *none* of its states — same shape as the S20
   `.gov` domain gate. Multi-campus universities map to a *set* of states (`midwestern.edu` → {AZ, IL},
   `touro.edu` → {NY, NV}) so a legitimate branch is never rejected; a domain absent from the snapshot falls
   back to the page-text rule honestly (flag/low, never asserted). NCES/IPEDS was firewalled from this host;
   the Scorecard institution ZIP on `scorecard.network` was reachable and authoritative.

4. **Junk page TYPES cap to low, never promote (bucket C).** News/press/event/media/blog/business-directory
   subdomains + path segments, plus a long-headline-slug heuristic (a final path segment of ≥10 hyphen
   tokens is a headline, verified against the 622 as press-release/news/job-posting with zero legitimate
   department pages). A match caps confidence to low — a junk *page type* can never be high, same shape as
   the existing topic-relevance cap. The headline-slug rule is exempted under `/departments|services|
   programs|resources/` (a long slug there is a spelled-out department name, not a headline).

5. **Trust-first sort (the deliverable's ordering).** At 68 rows / 5 geos a geo-first sort was fine; at
   622 / 72 it buried the value. Re-sorted contact-trust (high→low) FIRST, then population desc, then geo, so
   the high-trust rows outreach can act on sit at the top of what the client opens.

6. **Population — surface invalid-key failures loudly (bucket E).** The gap was not a matching bug (FIPS
   covers every state) — the 8 blank states simply had no cache from the crashed S21 run; re-looking them up
   fills all 8 with the real ACS5-2024 figures (Alabama 5,086,768, verified against the live API). While
   diagnosing, the Census API intermittently returned a 200 HTML "Invalid Key" page under load, which the
   client's `resp.json()` was swallowing as a misleading silent not_found; added a fail-loud path (a
   `census.invalid_key` warning + a clear result note) so a genuinely bad key can never again hide as a
   population gap. Populations are never fabricated.

7. **Re-derivation over a full re-run (the rewrite mechanics).** There is no page-content cache, so a literal
   pipeline re-run would re-fetch ~2,500 pages live (the fragile ~2h run that crashed in S21) and inject ~11
   days of page drift that muddies before/after attribution. Instead the four fixes were applied to the
   frozen S21 output by running the ACTUAL fix code (`university_states`, `phone_contradicts_geo`,
   `_is_junk_page`, `CensusClient`) over each row — faithful (real code paths), 0-drift, 0-billed, and
   cleanly attributable per bucket. Trade-off: a dropped wrong-geo phone is blanked, not replaced with an
   in-geo alternate (that needs a re-fetch) — the primary email contact is unaffected.

8. **Outreach preserved on rewrite (ADR-022 make-or-break).** Survivors are UPSERTED (the upsert never
   touches the user-owned outreach columns) and only the 29 wrong-state rows are deleted — proven end-to-end:
   a survivor seeded `contacted` in the DB kept its status/notes/author through the rewrite.

### Adversarial verification found (and fixed) 3 false positives

Four independent auditors web-verified all 118 changes. Buckets B (21/21) and the new-defect hunt were
clean. Three false positives were caught and fixed: `wbu.edu`/Hawaii and `widener.edu`/Delaware — real
physical branch campuses (Wayland Baptist Kapolei; Widener Delaware Law School) that the Scorecard
single-state row missed → added a small evidence-cited `_BRANCH_CAMPUS_STATES` override, restoring both;
and `ucop.edu`/California — a genuine `/departments/` CAPS page whose long slug is the department name, not a
headline → the resource-path exemption above. Final removals 31→29, caps 16→15.

### Result (0 billed)

622 → **593 rows**. Contact-trust high 77→71, medium 146→141, low 399→381. Population blanks 74 → 20 (all
remaining are city/neighbourhood geos honestly absent from Census). Master Sheet + Postgres rewritten,
idempotent, high-trust rows at the top. **504 tests** (416 unit + 58 db/api + 30 frontend); ruff + pyright
clean. Residuals (honest): an in-state third-party phone area-code cannot catch (already low); ~9% of `.edu`
absent from Scorecard fall back to text; a wrong-geo phone is blanked not replaced.

## ADR-025 — P0 hardening: single source of truth, server-side list, cost rails, data scrubs

**Date:** 2026-07-22
**Status:** Accepted
**Context:** A 30-agent QA audit (adversarially verified, 24 serious findings, 0 refuted) found the engine
solid but the product-around-it had workflow-breaking bugs, a split-brain deploy flaw, and data items the
client would personally trip over. This ADR fixes ONLY the P0 set — the things that fail the client's first
hour. P1 (hosting) and P2 (quality-of-life) are deferred. 0 billed; TDD throughout; outreach preserved
(ADR-022); nothing that worked broke.

### The root cause: two writable sources of truth

Postgres AND the Sheet were both authoritative writers. That single fact spawned the split-brain scheduler,
the header-wipe, and race-duplicate rows. **Decision: Postgres is the single source of truth; the Google
Sheet is a pure export (a projection of the DB).** The fixes below all descend from this.

### Decisions

1. **The scheduler persists to Postgres, not just the Sheet.** The Docker scheduler (`runner.py`) wrote the
   Sheet only, so a 3am-discovered prospect never reached the DB the dashboard reads. It now
   `persist_pipeline_run` (prospects + a run row) BEFORE exporting to the Sheet — the upsert preserves
   outreach (ADR-022), so a re-run of a known geo never clobbers a note. The API path already did this.

2. **The Sheet writer refuses a destructive rewrite (`_safe_rewrite`).** A drifted header (a client editing
   a column) or a short run used to trigger a full clear+rewrite with only the current run's rows — wiping
   the deliverable — and the clear→update was non-atomic. Now: a rewrite that would SHRINK the tab is refused
   unless `allow_shrink=True` (deliberate corrections opt in); the write is in place from A1 (no empty-tab
   window), clearing only the trailing band on an allowed shrink.

3. **Search + sort are server-side over the WHOLE dataset.** The dashboard's search filtered only the loaded
   50 rows (so a real prospect on page 2 read "no prospects match"), and column sort re-ordered only the
   page while the server default was geo-alphabetical (burying the 71 high-trust rows the S24 Sheet-sort
   fixed). Now `?search=` (ILIKE across website/geo/email/description) and `?sort=&sort_dir=` hit Postgres;
   the default order is trust-first (CASE rank so "low" doesn't sort before "medium" — the first-click
   low-first bug); the React table is controlled (no client reorder); the search box is debounced.

4. **Run concurrency + a global daily budget (`run_rejection_reason`, shared by API/scheduler/CLI).** Nothing
   stopped two "Run now" clicks or a Run-vs-scheduler collision from double-spending SerpAPI and racing the
   Sheet, and the budget cap was per-run (the CLI had none at all). Now a run is refused (409) when one is
   already `running` or when the last 24h of recorded runs have spent `MAX_BILLED_SEARCHES_PER_DAY` (new
   setting, default 320). The frontend disables "Run now" while a run is active and surfaces the 409 reason
   verbatim (the client now parses the error `detail`). The CLI gained the per-run circuit breaker it lacked.

5. **Data scrubs the client would trip on (deterministic, evidence-driven).** `clean_email` strips a leaked
   `mailto:` scheme, keeps the first recipient of a multi-recipient href, and URL-decodes (`%20`) — killing
   the 3 malformed emails that broke a mail-merge. A `_NATIONAL_HOTLINES` blocklist (988 Lifeline / SAMHSA /
   DV) drops a national crisis line published as an org's phone (an outreach rep would have called the
   Lifeline) — 7 rows. `irs.gov` joins `FEDERAL_DOMAINS`. `dconc.gov` (Durham County NC, verified) joins a
   tiny `_KNOWN_GOV_STATES` override so the scorer hard-rejects it when served to a CA geo. The live DB was
   scrubbed in place (discovery columns only — outreach untouched) and the federal/wrong-geo leaks deleted
   by the general rule `is_federal(website) OR candidate_state(website) ≠ geo state` (caught exactly the 4
   named rows, no over-deletion), then the DB was re-exported to the Sheet.

### Verified (0 billed)

**Backend 435 + db/api/scheduler 72 + frontend 33 tests**, ruff + pyright + build clean. Live (Playwright):
search "uwyo" now returns the row (was "no prospects"); the dashboard opens on high-trust rows; the Trust
header sorts high-first; the 3 malformed emails are cleaned (`cloy.tobola@ndscs.edu`, `vb311@vbgov.com`,
`info@cumberlandmaine.com`), 0 hotline phones remain, irs.gov + dconc.gov are gone; a second `POST /runs`
while one runs → 409; the header-drift/shrink guard refuses a wiping rewrite. **Make-or-break:** a survivor
seeded `contacted` survived the in-place scrub with its note + author intact (ADR-022). DB + master Sheet
**593 → 589 rows** (4 leaks deleted), idempotent, high-trust-first, dataset reset to 589/589 not_contacted.

### Deferred (still open — NOT P0)

P1 hosting (production compose for API+frontend, migrations-on-boot, DB backups, loopback pg bind + real
password, `AUTH_COOKIE_SECURE`, Sentry DSNs, session revocation). P2 quality-of-life (bulk outreach, URL
routing, outreach columns in the CSV export, Export-Sheet outreach filter + scratch workbook, org-level
dedupe view, session-expiry UX, note-conflict guard). The scheduler holds no `running` row during its own
pipeline, so the API↔scheduler mutual exclusion has a narrow window bounded by the daily budget cap.

## ADR-026 — Local username/password sign-in + a public landing page

**Date:** 2026-07-29
**Status:** Accepted (supersedes the Google sign-in of ADR-018)
**Context:** Teammates were not comfortable handing a Google account to the tool, and the ADR-018 flow
also required a Google Cloud project, an OAuth consent screen, and every teammate added as a "test
user" before they could log in. That is heavy machinery for an internal tool with a handful of users,
and it made the front door the most awkward part of the product. Separately, the app had no public
face at all: an unauthenticated visitor saw only a bare login card.

### Decisions

1. **Local credentials, no third-party identity.** `POST /auth/login` takes a username and password,
   verifies against `AUTH_USERS` (`username:<scrypt hash>` pairs), and mints the SAME signed session
   JWT in the SAME httpOnly cookie as before. Everything downstream is untouched: `get_current_user`,
   the guarded data routers, and the pipeline/CLI/scheduler (which never touch the HTTP API).
2. **scrypt from the standard library, not a new dependency.** `hashlib.scrypt` (n=2^14, r=8, p=1) is
   a memory-hard KDF, salted per password, compared with `secrets.compare_digest`. No plaintext is
   stored or logged. Chosen over bcrypt/argon2 to avoid adding a dependency for one function.
3. **No user enumeration.** An unknown username still runs a verify against a dummy hash, so the work
   (and the response time) matches a wrong password, and both return the identical message.
4. **Brute force is throttled.** A password form is guessable in a way an identity provider was not,
   so failures per (client, username) are counted and locked out for `AUTH_LOCKOUT_MINUTES` after
   `AUTH_MAX_FAILED_LOGINS`. The counter lives on the app instance, not in module state, so tests and
   multiple apps in one process never share a lockout. A shared store is the upgrade if this ever
   faces the open internet.
5. **Identity is now `username`, not `email`.** `AuthUser.username` is what gets recorded as
   `outreach_updated_by`, so the ADR-022 attribution still answers "who marked this contacted".
6. **Accounts are minted by a CLI, never typed into a config by hand.**
   `authority_finder.cli create-user` prompts for the password (hidden, confirmed) so it never lands
   in shell history, and prints the one line to paste into `AUTH_USERS`.

### The landing page

A signed-out visitor now gets a real product page instead of a login card, built on the workspace's
own token system (teal on slate, Inter, the existing card/badge language) so the two halves read as
one product. The concept extends the logomark: the logo is a radar scope, so the hero is a sweep
lighting up the authority sites it finds.

**Every figure on the page is read from the live dataset** (589 prospects, 70 geographies, 71 high
trust, 364 with email, 82 already linking to a competitor, 29 mis-filed rows removed in the S24
audit), and the wrong-state examples (`vaughn.edu` under Alaska, `tamiu.edu` under Hawaii,
`dconc.gov` under Irvine) are real catches from that audit. The product screenshot is a real capture
of the running workspace, not an illustration. Nothing on the page is invented.

Motion is limited to three things that each carry meaning: the radar sweep (the product's actual
job), one reveal per section as it enters, and a single marquee for the 16 competitor domains (a list
that needs breadth, not individual attention). All of it stops under `prefers-reduced-motion`, and
reveals fall back to visible when IntersectionObserver is unavailable or a fast scroll skips a
section, because content must never be hidden by a missing API.

### Verification

**444 backend + 33 frontend tests**, ruff + format + pyright + build clean. Live: `admin` signs in
through the dialog and lands in the workspace showing the real 589 rows; a wrong password returns one
generic message; the lockout message surfaces verbatim; logout returns to the landing page. Checked
at 1440px and 375px (no horizontal scroll), in both dark and light themes.

### Trade-off

Password auth puts credential handling on us rather than on Google: no MFA, and a leaked password is
a direct compromise. For an internal tool of a few users behind an admin-created account, the drop in
friction is worth it. Sessions still cannot be revoked before expiry (a P1 item carried over from the
QA audit), and passkeys remain the natural upgrade once the tool is hosted over HTTPS.

## ADR-027 — Component 3: authority filter (DR as a signal, not a gate)

**Status:** accepted (2026-07-30, sessions 27–32). Supersedes the component-3 approach sketched
in the brief's Challenge 3.

**Context.** Component 3 — "high authority resource sites like ncala.org" — was the one brief
component never built, skipped since ADR-003 for lack of an Ahrefs API key. Jake supplied a key,
so it became buildable. The brief's mitigation reads: *"Ahrefs API — filter by Domain Rating
above an agreed threshold (e.g., DR 40+)."*

### Decision 1 — unrestricted queries are required, and they are a new problem

Discovery's templates are scoped `(site:.gov OR site:.edu)`, so they can never return an
organization like ncala.org. That is why ADR-006's `other` classification bucket was
instrumented, counted, and returned zero on every run for months. Component 3 therefore needs
its own unrestricted query set (`authority_filter/queries.py`).

Dropping the `site:` filter admits the open web. A DR threshold cannot clean that up: the live
Alabama/Texas run returned facebook.com at DR 100, instagram.com 100, linkedin.com 99, yelp.com
94, prnewswire.com 92, guidestar.org 91. **The failure mode is wrong TYPE, not low authority**,
and raising the floor makes it worse — it keeps every social network and cuts the small local
orgs we want. Hence `platforms.py`, applied BEFORE any Ahrefs call so junk never costs units.

### Decision 2 — DR is a displayed signal, not a pass/fail gate

Two independent bodies of evidence, both against the brief's DR 40.

*Calibration* (20 real behavioral-health orgs): ncala.org 34, txcouncil.com 32, calbhbc.org 29 —
real state-level bodies, all rejected at 40, while every national org clears it easily. For a
geo-targeted tool that is backwards: a state coalition is worth more than a national body,
because the national one is not specific to the geo page.

*Ground truth* (`docs/competitor-backlink-analysis.md`) — mining the referring domains of
rehabnet.com, recovery.com and addictioncenter.com, which is the method the brief itself
specifies. Of 531 candidate-class referring domains in the DR 5–45 band:

```
min 5 | p25 11 | median 20 | p75 30 | max 45
DR>=40  8%   DR>=25  40%   DR>=20  50%   DR>=10  79%
```

**The median organization that demonstrably links to a working directory scores DR 20.** DR 40
would discard 92% of them.

So DR does not gate. Selection is by type (blocklist + commercial filter) and geography (the
existing ADR-020/024 gates). DR rides along as a value for the outreach rep.

A sampling lesson worth recording: on a backlink profile, ordering by `domain_rating:desc`
returns national media and cloud infrastructure, `:asc` returns bare IP addresses. Local
organizations live in neither tail — always band-filter with `where`.

### Decision 3 — commercial treatment providers are filtered on content, not by domain

With DR removed, for-profit facilities dominated the residual junk (~57% precision). They are
real orgs, with real pages, in the right geo, so every existing gate passes them — but a
facility marketing its own treatment services competes for the same backlinks. It is a
competitor, not a prospect.

A domain list cannot express this: `txcouncil.com` is the Texas Council of Community Centers
and `whitesandstreatment.com` is a for-profit rehab. So `commercial.py` reuses the ADR-024
technique and judges the page by what it says about itself, with **asymmetric grading** because
the errors do not cost the same — losing a real coalition is worse than admitting one facility:

- a facility self-description ("treatment center", "residential treatment", "levels of care")
  is decisive alone;
- a direct-response CTA is not — real nonprofits publish phones and say "get help" — so two are
  required.

It runs on title+snippet, so rejecting a facility costs no fetch. Result: precision 57% → ~82%
with **zero false positives** across the 5 validation geos; 12/12 must-keep orgs retained,
including northalabamamentalhealthcoalition.org at DR 8.

One miss is accepted and pinned by a test rather than hidden: `markbehavioral.com`
("Mental Health Treatment in Clearwater | Call MBH Today"). Catching it requires treating
"mental health treatment" as decisive, which a real nonprofit could legitimately say.

### Decision 4 — the primary ranking signal is proven directory-listing behaviour

`link_checker` (ADR-011) already detects orgs linking to the 16 competitor directories. An org
that already lists a directory has **demonstrated** it will list one — stronger than any
inferred property such as contact trust or DR. Those rows now sort first in both the sheet
(`csv_writer._sort_key`) and Postgres (`repository._order_by`), ahead of the ADR-024 trust-first
order. On the live 589-row dataset, 82 rows carry a competitor link and now lead.

### Decision 5 — gate reuse is structural, not promised

Authority candidates are emitted as ordinary `CandidateSite` objects with
`domain_class="other"` and merged into `DiscoveryResult.candidates` **before** detection. There
is no separate authority code path, so wrong-state validation, junk-page detection, the hotline
blocklist and contact-trust banding cannot be bypassed. The feature skips cleanly when no
Ahrefs key is configured.

### Correction recorded

`ncala.org` was assumed (by me, in session 27) to be an Alabama addiction council. It is the
**North Carolina Assisted Living Association** — assisted living, North Carolina. The brief
pairs it with dbhdduniversity.com, so the target class is **care-adjacent local organizations**
(assisted-living and health-care associations, developmental-disability councils, aging
services, provider networks), not only addiction councils. Query themes were widened
accordingly, after which ncala.org surfaces at DR 34.

### Cost

Ahrefs bills `max(50, per_row_cost * rows)`, and `/site-explorer/domain-rating` accepts no
`select`, so it always floors at 50 units **for one domain**. `/batch-analysis` takes 100
targets and measured 60 units for 20 — roughly **17× cheaper per domain**. Always batch.
Responses are cached to `data/cache/ahrefs/` (ADR-005 pattern), so re-runs cost nothing.

### Deviation from the brief, stated plainly

The brief says DR 40+. We ship DR as a signal with no threshold. The justification is the two
evidence sets above. `AHREFS_DR_THRESHOLD` remains configurable if the client wants a floor
reinstated. **This is a deliberate, documented deviation and needs client ratification.**

## ADR-028 — Geo derivation for non-.gov candidates

**Status:** accepted (2026-07-30, session 36). Extends ADR-020.

**Context.** ADR-020 derived a candidate's state only from `.gov`/`.us` domains, which was
correct while every candidate came from `site:.gov OR site:.edu` discovery. Component 3
(ADR-027) added an unrestricted authority source whose candidates are overwhelmingly `.org`
and `.com`, so **the domain-level geo check did nothing for the majority of new candidates** —
only the weaker text heuristic applied.

The defect was not theoretical. `mhaorangeny.com` — the Mental Health Association of Orange
County **New York** — reached output filed under **Orange County, California**.

**Decision.** `candidate_state()` now derives a state from non-.gov registrable domains, by
two rules, both refusing rather than guessing:

1. **Full state name** appearing in the label (`northalabamamentalhealthcoalition.org` → AL,
   `thearcoftexas.org` → TX). Two different state names in one label (`montana-...-in-ohio`)
   asserts nothing.
2. **A two-letter code as an anchored SUFFIX**, restricted to a small allowlist.

Rule 2's allowlist is the important part. Most state codes are ordinary English word endings,
and a wrong assertion causes a *hard reject* — it deletes a real prospect. The traps are real,
drawn from live data:

```
txcouncil.com   ends in "il" -> would file the Texas Council under ILLINOIS
lacounty-vendor ends in "or" -> Oregon        information -> "in" Indiana
medicare        ends in "re"; "me" Maine      pathways    -> "pa" Pennsylvania
identity        -> "id" Idaho                 community   -> "co" Colorado
```

So only codes that essentially never terminate an English word are read as bare suffixes:
`ny nc tx nj nv wy sc vt wv mn az nm nh sd`. A *leading* code (`txcouncil`, `nccdd`) is never
read — that would be the substring match this ADR exists to avoid. `.edu` remains excluded;
its geography comes from the College Scorecard dataset (ADR-024).

**Measured on the 213 real end-to-end rows:** 46 domains now positively confirm their target
geo (a signal that did not previously exist), exactly **1 contradiction is caught —
`mhaorangeny.com`** — and **0 legitimate orgs are wrongly contradicted**.

**Known limitation, recorded not hidden.** A full state name used as a street or personal name
(`delaware-street-clinic.org`) resolves to that state. Full names are a much stronger signal
than two-letter codes and are worth keeping, but they cannot distinguish a state from a street.
Pinned by a test so the trade-off is visible. If it appears in real data, require the name to
sit adjacent to an org token rather than anywhere in the label.

## ADR-029

**The `.gov` half of discovery is a lookup, not a search.**

Discovery was paying Google, per geo, to answer "which `.gov` sites exist here?" — while CISA
publishes the complete list of US `.gov` domains for free. Vendored as `data/gov_domains.csv`
(16,406 rows) behind `discovery/registry.py`, which collapses the `site:.gov` queries to zero
billed searches and leaves the paid budget for the `.org`/`.com` authority source, where an
enumerable registry does not exist.

Validated against the live 589-row dataset BEFORE building, not after: all 266 `.gov` domains
discovery had ever found are present — 208 exact, 58 as their parent (`hhs.nd.gov` → `nd.gov`),
zero missing. The parent-domain case costs nothing because `page_detector`'s bounded crawl
already walks a root down to the department page, which is precisely what the paid query was
buying.

**Vendored, not fetched at runtime.** A 3am scheduled run must not fail because an external
host is down. Refresh is a documented manual command in the module docstring.

Matching rules were derived from the real data rather than assumed: a County row's `City`
field holds the county SEAT (`pinellas.gov` is City=Clearwater), so counties match on
`Organization name` and cities on `City`.

## ADR-030 — Scheduler moves from an interval to day-of-week cron

**Status:** accepted (2026-07-31).

**Context.** The scheduler fired on `IntervalTrigger(hours=RUN_INTERVAL_HOURS)`. An interval is
not what an operator means by a schedule: a 24h interval started at 14:00 keeps firing at
14:00, and every container restart permanently moves the slot. The client asked for Mondays and
Wednesdays.

**Decision.** `CronTrigger` with named days at a fixed local time, configurable, defaults
`RUN_DAYS=mon,wed` and `RUN_TIME=03:00`.

Parsing lives in `scheduler/schedule.py`, separate from APScheduler, so the rules are testable
without a scheduler running. An unknown day or malformed time raises rather than defaulting —
a typo must never yield a scheduler that silently never fires.

**Timezone is the client's, not the server's.** `RUN_TIMEZONE` defaults to `America/New_York`,
NOT UTC. The run exists to have fresh prospects waiting at the start of the client's business
day. Under UTC a 03:00 job lands at 22:00 or 23:00 their previous evening depending on season,
and shifts twice a year as US daylight saving moves while UTC does not. Pinning to an IANA zone
makes 03:00 mean 03:00 to the people reading the output, summer and winter.

`RUN_INTERVAL_HOURS` is retained in settings as deprecated so an existing `.env` keeps loading,
but no longer drives anything. The `--interval-hours` CLI flag was REMOVED rather than left
inert — a flag in `--help` that changes nothing is a lie. `--days` and `--at` override per
invocation.

**Unchanged:** every cost rail survives — zero spend when no new geos, `MAX_NEW_GEOS_PER_RUN`,
the `MAX_BILLED_SEARCHES_PER_RUN` circuit breaker, the daily ceiling, and the no-concurrent-run
guard. This ADR changes only *when* a tick fires, never what a tick may spend.

## ADR-031

**Sitemap coverage: match topic-prefixed geo URLs, and count what the parser cannot read.**

Both sites publish geo pages under content-type prefixes (`/support-groups/…`,
`/ocd-treatment/…`) that the single primary `geo_url_regex` never matched. The corpus was
reported as "AH is state-only" and accepted as fact until the user challenged it. It was wrong:
**9 AH and 2,848 MHD geo pages were live and invisible**, and the corpus corrected 5,958 →
6,263.

Two changes, and the second matters more than the first:

1. `SiteConfig.topic_url_regexes` — additional shapes tried in order after the primary. The
   parser keeps the first VALID parse rather than the first regex MATCH, so a shape that
   matches but yields a non-whitelisted state does not shadow one that would have parsed.

2. **Unparsed URLs are counted and logged with an example** (`summarise_unparsed`). The real
   defect was not the missing pattern — it was that a URL the parser could not read produced
   silence, making "no such pages exist" indistinguishable from "we cannot read them". A
   filter that discards without counting cannot report its own blindness, which is why this
   needed a human to notice. Same principle as ADR-006's drop-but-COUNT.

US territories (PR, GU, VI, MP, AS) and DC were added to the state whitelist at the same time;
the instrumentation is what surfaced them. The site's `district-of-colombia` misspelling is
accepted alongside the correct one — their URL, not ours to correct.

## ADR-032

**Competitor link provenance: name the page the links are actually on.**

The client opened row 1 of the master Sheet (`ucr.edu`), saw `Competitor Links =
addictionresource.net; samhsa.gov`, opened `Specific Page = https://counseling.ucr.edu/`,
found no competitor links anywhere on it, and reported the row as a false positive.

Verified with Playwright before changing anything. The client was right about the page and
wrong about the row:

| Page | Links | External | Competitor hits |
|---|---|---|---|
| `counseling.ucr.edu/` | 112 | 17 | **0** |
| `counseling.ucr.edu/resources-support-…` | 378 | 164 | **3** |

The three are `findtreatment.samhsa.gov`, `samhsa.gov`, `addictionresource.net` — exactly the
stored value. The detection was correct. **The deliverable just never named the page.**

ADR-011 checks the detected page AND one resources hop, by design: an org's outbound links
live on its resources page, not its contact page. So the two columns were describing different
pages while sitting side by side, and the row could not be verified by the person reading it.

**Decision: append `Competitor Links Found On`, populated only when it differs from
`Specific Page`.** Blank keeps meaning "the same page", so blank needs no explanation and a
value only appears when it tells the reader something they could not otherwise work out.

`Specific Page` STAYS the contact page — it is the outreach target, and repointing it at the
resources page would fix the audit at the cost of the column's actual job.

**Scale of the problem:** re-checking all 268 competitor-linked rows found **100 (37%)** whose
links are on a page other than the one shown. Every one of those would have read as a false
positive. The re-check also corroborated the original detection: **266/268 domain sets matched
exactly**, 1 fetch failure, 1 page changed since the run — so provenance was written only where
the links were still confirmed, never asserted from a fetch that could not verify them.

**The meta-decision — a structural guard, not a third patch.** This is the third field captured
by the pipeline and silently dropped before the client saw it:

1. the `other` discovery bucket (ADR-006) — counted, then discarded
2. `domain_rating` — accepted by `build_row` and never assigned; later missing from
   `upsert_prospect`'s explicit column list, so the CSV held 1,241 values and every DB row NULL
3. `found_on_url` — set on every `CompetitorLink`, read by nothing

Each was found by a human reading the output, twice by the client. `tests/output/test_field_paths.py`
now asserts the wiring structurally: header width matches the model, `build_row` assigns every
parameter it accepts, and every pipeline-owned field appears in BOTH the INSERT values and the
on-conflict `set_`. Those tests were written first and immediately caught this same field
missing from the DB path. The outreach fields are asserted ABSENT from the conflict set_, so
the guard cannot be satisfied by weakening ADR-022.
