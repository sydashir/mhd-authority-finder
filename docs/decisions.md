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
