# Discovery cost — options, arithmetic, and a recommendation

**Status:** decision input, not a decision. Written 2026-07-31 (session 37) from four parallel
research streams, re-grounded against this repo at HEAD (`1b83bae`).

**Scope:** the DISCOVERY input only — "give me candidate domains for this geo". Everything
downstream (page detection, contact extraction, geo validation, junk gates, link checking) is
built, tested, and unchanged by every option below.

---

## 1. The problem in three sentences

Discovering candidates for all **5,958 geo pages** (99 state / 2,097 county / 3,762 city) costs
**$1,081 in SerpAPI charges** for one full pass, and the client will not authorise that.
The bill is not caused by an expensive vendor — it is caused by **72,090 individual searches**,
of which **53,721 (74.5%) are `site:.gov` / `site:.edu` queries that ask Google a question two
free registries in this repo already answer**.
The decision is therefore not "which SERP vendor is cheapest" but "how many searches do we
actually need to buy", and the honest answer is that the cheap part of coverage is nearly free
while the last slice of coverage genuinely costs money.

### The baseline reconciles exactly — this is a VERIFIED number, not a client estimate

The `$1,081` figure was not taken on trust. It reproduces exactly from the templates at HEAD:

| Level | Geos | `discovery/queries.py` (all `site:`-restricted) | `authority_filter/queries.py` (no operator) | Searches |
|---|---:|---:|---:|---:|
| State | 99 | 10 | 8 | 1,782 |
| County | 2,097 | 9 | 3 | 25,164 |
| City | 3,762 | 9 | 3 | 45,144 |
| **Total** | **5,958** | **53,721 operator queries** | **18,369 operator-free** | **72,090** |

`72,090 × $0.015 = $1,081.35`. **VERIFIED** — template counts read from
`src/authority_finder/discovery/queries.py` and `src/authority_finder/authority_filter/queries.py`
at commit `1b83bae`; unit price is SerpApi's Developer tier ($75 / 5,000), fetched live from
[serpapi.com/pricing](https://serpapi.com/pricing) on 2026-07-31.

Because the baseline reconciles to the digit, every saving below is measured against a real
number rather than a guess.

### Two corrections to the research, up front

The four research streams were commissioned against the brief, not against HEAD, and **two of
their headline findings are already out of date or wrong**. Both would have cost real money.

**(a) "The pipeline is structurally blind to .org/.com" — FALSE at HEAD.** Two streams
independently made this their headline: 28 of 28 templates carry `site:`, therefore 9 of the
client's 12 validated good finds can never be returned. That was true until 2026-07-30.
**ADR-027 shipped `authority_filter/` with 14 unrestricted templates** and its own commercial
and platform filters; `pipeline.py:120` already merges those candidates before detection.
The single largest "opportunity" in the research is **already built**, and its cost is already
inside the $1,081 (it is the 18,369 operator-free queries above). Do not pay for it twice.

**(b) "DataForSEO takes this to $32" — WRONG by 5x on 74% of the queries.** One stream
recommended DataForSEO at a flat $0.0006/search. DataForSEO's own documentation says
otherwise, and I verified it against two of their pages independently:

> "if this field contains such parameters as `'allinanchor:'` … `'site:'`, **the charge per task
> will be multiplied by 5**"
> — [docs.dataforseo.com task_post](https://docs.dataforseo.com/v3/serp/google/organic/task_post/),
> corroborated by [their cost help-centre page](https://dataforseo.com/help-center/serp-api-cost-explained). **VERIFIED**

Applied to our actual template mix, DataForSEO Standard is `53,721 × $0.003 + 18,369 × $0.0006`
= **$172.18**, not $32 — and DataForSEO *Live* mode (the only mode that preserves our
synchronous client) is `53,721 × $0.01 + 18,369 × $0.002` = **$573.95**, which is *worse than
switching SerpApi to its Big Data tier*. This is precisely the failure mode this project has
already hit twice, caught before commitment rather than after.

### The reframing that matters most

The corpus is **already fully published** — a live sitemap fetch returned 5,962 MHD geo pages
against the 23 recorded in `data/state/mhd.json`, i.e. the client shipped the entire US
county+city set in one publish event (VERIFIED by live fetch; stream C). So **$1,081 is a
one-time backfill, not a recurring bill**. The ADR-012 incremental scheduler already spends
nothing when no new geos appear. At an ESTIMATE of ~500 new geo pages/year, steady-state cost
on any option below is **single-digit to low-double-digit dollars per year**.

Optimise the backfill. The recurrence is already solved.

---

## 2. Options analysis

Every option is costed on the same 5,958-geo corpus and the same template mix, so the numbers
are directly comparable. Prices carry VERIFIED (I fetched the vendor page or ran the query) or
ESTIMATE (reasoned, third-party, or unmeasured).

---

### Option 1 — Registry-first: stop buying `.gov` / `.edu` search

**What it is.** Delete the 53,721 `site:`-restricted queries and seed those candidates from two
datasets already vendored in this repo: the CISA `.gov` registry (`data/gov_domains.csv`,
16,406 rows, `discovery/registry.py`, ADR-029, committed yesterday in `1b83bae`/`6f9a946`) and
the College Scorecard `.edu` set (`data/university_states.csv`, ADR-024).

**How it works here.** `registry.domains_for_geo(state=, county=, city=)` already returns
`.gov` domains most-specific-first and is already tested. The work is in `discovery/discover.py`:
merge a free registry candidate stream with the paid authority stream into the same
`DiscoveryResult.candidates` list. Downstream is untouched — this is the identical structural
trick ADR-027 used for authority candidates, so gate-reuse is guaranteed rather than promised.

**Cost at 5,958 geos.** Paid searches fall from 72,090 to the 18,369 operator-free authority
queries.

| Vendor | Arithmetic | Cost |
|---|---|---:|
| SerpApi Developer (status quo) | 18,369 × $0.015 | **$275.54** |
| SerpApi Big Data | 18,369 × $0.00917 → but quota is 30,000/mo, so 1 month | **$275.00** |
| DataForSEO Standard (no operators now) | 18,369 × $0.0006 | **$11.02** |
| Serper | 18,369 credits, one $50 pack | **$50.00** |

VERIFIED on unit prices (SerpApi and DataForSEO pages fetched 2026-07-31; Serper's own pricing
page 404s — $50/50k credits is ESTIMATE from four independent trackers).

**Coverage vs current — the honest part, and it is not free.** The brief already measured CISA
at **~38% direct hit** (16% exact + 22% parent-domain seed) when asked "return the right domain
for THIS geo". That 38% headline understates it in one direction and overstates it in another:

- *Understates:* the 22% parent-domain case (`hhs.nd.gov` → `nd.gov`) is not a miss.
  `page_detector`'s bounded crawl (≤6 fetches) exists precisely to walk a root to a department
  page — that is what the paid search was buying. `registry.py`'s own docstring records that
  **all 266 `.gov` domains the live 589-row dataset ever found are present in the registry**
  (208 exact, 58 as parent, zero missing). VERIFIED against the production dataset.
- *Overstates:* stream C ran `domains_for_geo` against all 27 MHD Orange County cities and got
  the city's own `.gov` for 20/27 = **74%**, leaving **26% of cities with no city-hall row**.
  It also found real fuzzy-match noise (`villa-park` → `baldwinparkca.gov`;
  `huntington-beach` → `hermosabeach.gov`), which costs crawl budget and can leak wrong-geo rows.

**Net:** `.gov` coverage moves from search-derived to registry-derived and drops modestly; `.edu`
is roughly flat (the Scorecard set is ~90% corpus coverage, ADR-024); `.org`/`.com` is unaffected.

**Effort.** ESTIMATE 1–2 days. `registry.py` and the Scorecard lookup exist and are tested; this
is a merge in `discover.py` plus a per-geo cap and ranking pass.

**Ongoing maintenance.** Low. One `curl` to refresh `data/gov_domains.csv` (already documented in
`registry.py`). No adversarial surface — it is a static federal CSV, not a scraped endpoint.

**Risks and failure modes.**
- **The real cost is transferred, not eliminated.** The brief already identified this trap: a
  state-wide registry scope returns hundreds of candidates per geo, trading search cost for
  fetch cost. `domains_for_geo` returns city + county + *all state-level* rows, so a per-geo cap
  and a ranking pass are mandatory, not optional.
- 26% of cities lose their own city-hall domain (VERIFIED on one county, n=1, ESTIMATE nationally).
- Fuzzy token matching produces wrong-geo candidates; ADR-020's wrong-state gate catches them
  but they still consume fetch budget.
- The registry is vendored, so it goes stale between refreshes.

---

### Option 2 — County → city inheritance

**What it is.** The 3,762 city geos inherit their county's discovered candidates instead of
running their own searches. This is **not** the state→city reuse the team already measured and
rejected.

**How it works here.** Two structural facts make it nearly free: **100.00% of city pages have
their county page present** in the corpus, and the county is literally in the URL
(`/serving/california/orange/anaheim`), already parsed by `geo_monitor/url_parser.py`. So there
is zero geocoding and zero ambiguity. Process counties first, key results by `(state, county)`,
have city geos read that key. Cities still run their own detection, extraction, link check and
population lookup, so **output rows stay per-geo**. VERIFIED (live sitemap parse, stream C).

**Why this differs from the rejected state→city test.** Stream C classified the 19 useful on-geo
domains from the cached Clearwater FL search by scope: **11 (58%) are county-scoped**, 6 (32%)
state-scoped, only 2 (11%) strictly city-scoped. Decisively, **`nami-pinellas.org` — the exact
org cited as proof that state→city reuse fails — is COUNTY-scoped.** The local chapter that a
state search misses is usually organised at county level, which is the level being inherited
from. VERIFIED from cached SERPs; ESTIMATE that it generalises (n=1 city).

**Cost at 5,958 geos.** Paid geos fall from 5,958 to 2,196 (99 state + 2,097 county). Stacked
with Option 1, paid searches = `99 × 8 + 2,097 × 3` = **7,083**.

| Vendor | Arithmetic | Cost |
|---|---|---:|
| SerpApi Developer | 7,083 × $0.015 | **$106.24** |
| DataForSEO Standard | 7,083 × $0.0006 = $4.25 (below $50 min deposit) | **$50 float** |
| Serper | one $50 pack | **$50.00** |

**Coverage vs current.** ESTIMATE, and the weakest-evidenced number in this document. Of
Clearwater's 19 useful finds, 17 (89%) are county-or-broader and survive; of the 2 city-only,
one is recoverable free from CISA, leaving **~5% genuine loss** — but that is **n=1**.

**Effort.** ESTIMATE 1 day. The lowest-effort high-multiplier lever available.

**Risks and failure modes.**
- The 5% loss figure is n=1 and will be worse where cities are large relative to their county
  (independent cities in Virginia; city-counties like San Francisco and Denver; New England
  towns with strong sub-county government).
- **Dedupe amplification.** The pipeline dedupes on `(website, geo_served)`, so one county org
  inherited by 79 Los Angeles County cities creates 79 rows for the same org. S25's QA audit
  already flagged "same org × N geos" as a finding — **this lever makes that worse** and needs
  the org-level dashboard view that is already on the P2 list.
- 79 cities sharing one prospect set may read as low-effort to the client even when each org
  genuinely serves each city. This is a client-perception risk, not a data-quality one.

---

### Option 3 — Vendor swap (DataForSEO or Serper)

**What it is.** The same queries at a lower unit price. No quality change by construction.

**How it works here.** `discovery/serpapi_client.py` is a clean seam: it takes `(query, gl, hl,
start)`, returns a `NamedTuple`, owns its sha256 disk cache and the `billed_search_count`
circuit breaker. A sibling client implementing the same interface is ~150–250 LOC. Note the
cost rails (`MAX_BILLED_SEARCHES_PER_RUN`, `MAX_BILLED_SEARCHES_PER_DAY`, ADR-025) assume
SerpApi semantics and must be re-denominated.

**Cost at 5,958 geos, current templates unchanged (72,090 searches):**

| Vendor / mode | Arithmetic | Cost | Verified |
|---|---|---:|---|
| SerpApi Developer (status quo) | 72,090 × $0.015 | $1,081.35 | VERIFIED |
| SerpApi Big Data | 72,090 ÷ 30,000 = **3 monthly quotas** × $275 | **$825.00** | VERIFIED |
| DataForSEO Standard (5x on 53,721) | 53,721 × $0.003 + 18,369 × $0.0006 | **$172.18** | VERIFIED |
| DataForSEO Live (5x on 53,721) | 53,721 × $0.01 + 18,369 × $0.002 | **$573.95** | VERIFIED |
| Serper | 72,090 credits → 2 × $50 packs | **$100.00** | ESTIMATE |

**The tier trap, stated plainly.** SerpApi sells a **monthly quota, not metered usage**. Naive
per-search arithmetic gives Big Data at `72,090 × $0.00917 = $661`, but you cannot buy 72,090
searches in one month on a 30,000 plan — the backfill costs **$825 across three months**, or
you split it over three billing cycles. Anyone quoting $661 is quoting a price that is not for
sale.

**Coverage vs current.** ESTIMATE: parity, since it is the same Google organic page 1. UNVERIFIED
in the one place it matters — **no stream ran a single live query against any alternative
provider**, and our queries lean hard on `site:` and quoted phrases, which is exactly where
thin parsers differ. DataForSEO's free city-level `location_name` targeting is arguably a
genuine *upgrade*: we currently pass `gl=us` only and stuff the geo into the query text.

**Effort.** ESTIMATE 1 day for Serper or DataForSEO Live (synchronous). 3–5 days for DataForSEO
Standard, whose task-queue model (POST task, poll, ~5 min) breaks the synchronous
`await client.search(q)` contract in `discover_many`.

**Risks and failure modes.**
- **Legal/continuity, and it is live.** Google sued SerpApi in Dec 2025; the DMCA claims were
  dismissed 2026-07-20 but Google is amending. The entire scraped-SERP category shares this
  exposure. Keep the client behind an interface so vendors stay swappable.
- Serper has no published pricing page (404s), no SLA, credits **expire after 6 months** — a bad
  fit for a bursty one-time backfill — and StatusGator logged 100+ outages since March 2025,
  with incidents through late July 2026. Our scheduler runs unattended at 3am.
- Silent degradation is the common 2026 failure mode: a 200 OK with a short result set quietly
  shrinks candidate sets rather than erroring.

---

### Option 4 — IRS EO BMF + Form 990 XML (free nonprofit registry)

**What it is.** Two free, public-domain IRS bulk files. The Exempt Organizations Business Master
File (1,983,563 orgs; NAME, CITY, STATE, ZIP, NTEE — **no website, no county**) joined on EIN to
the Form 990 e-file XML corpus, which **does** carry `<WebsiteAddressTxt>`.

**How it works here.** Filter BMF to on-target orgs, map ZIP→county with the free Census ZCTA
crosswalk, join to the 990 website index, emit `CandidateSite` rows into the existing
`DiscoveryResult`. This targets exactly the `.org` class the client validated.

**Cost at 5,958 geos.** **$0** licence, for all geos. ~250 MB BMF + ~3 GB/year of 990 XML,
parsed locally (147,058 filings parsed in ~100s on a laptop). VERIFIED — stream B downloaded and
parsed the real files rather than reading docs.

**Coverage — measured, and genuinely mixed.**

| Metric | Result | Basis |
|---|---|---|
| Counties with ≥1 on-target candidate | 537/546 = **98.4%** | VERIFIED, 5 states (NC/TX/FL/CA/AL) |
| Counties with ≥3 | 506/546 = **92.7%** | VERIFIED |
| Counties with ≥1 **free domain** | 295/546 = **54%** | VERIFIED but from a **4-month** 990 index |
| Counties with ≥1 free domain, full-year index | 80–90% | **ESTIMATE** — extrapolation |

**The single most important finding in this option:** filtering by **NTEE code silently destroys
the client's best prospects**. Of 10 validated good finds, only 2 survive an NTEE F/E/P filter.
`nchcfa.org` and `apnc.org` both have a **blank** NTEE. NTEE is blank for 24.8% of NC orgs, and
Florida NAMI chapters scatter across F30/F21/F80Z/P80Z/Z99/blank. A **name-keyword union** rule
recovers 6 of 6 of the BMF-present validated finds. VERIFIED.

**Effort.** ESTIMATE 4–6 days. **Ongoing:** low (two stable government URLs), except the keyword
regex, which is a tuned asset needing periodic human review.

**Risks and failure modes.**
- **Hard structural ceiling:** `ncsappb.org` (a state licensing board, not a 501(c)(3)) and
  `northalabamamentalhealthcoalition.org` (unincorporated) are **absent entirely**. BMF can never
  be the only source.
- BMF city is the **mailing** address, not the service area — PO boxes and directors' home
  addresses mis-file the geo. Unquantified precision risk.
- 990-N e-Postcard filers are absent, so the smallest, most hyper-local orgs never supply a
  website through this route.
- `WebsiteAddressTxt` is dirty: only 54% of populated tags parse to a usable domain.
- The well-known **AWS mirror is DEPRECATED** (stopped 2021-12-31); the live source is
  `apps.irs.gov`.

---

### Option 5 — Overture Maps Places (free POI dataset)

**What it is.** A free, CDLA-Permissive-2.0, 75M-place POI dataset with `websites`, `emails`,
`phones` and `confidence`, queryable from S3 with DuckDB.

**Cost.** **$0** licence; single-digit dollars of one-time egress. VERIFIED — stream D ran live
DuckDB queries against release `2026-07-22.0`.

**Coverage — measured.** **10 of 12** named good finds present with correct city/state
(including `nami-pinellas.org`, `nchcfa.org`, `apnc.org`, `txcouncil.com`, `sacada.org`).
**Misses the same 2** as IRS BMF: `ncsappb.org` and `northalabamamentalhealthcoalition.org` —
the small state boards and micro-coalitions the brief calls most valuable.

**Risks and failure modes.**
- Overture's own docs state Places "is known to contain duplicates, a high junk rate, and low
  property completeness".
- **Directly observed cross-geo contamination:** `montgomerycountymd.gov` attached to a Chinese
  restaurant in Philadelphia; `unh.edu` attached to a Clearwater FL dermatology practice. Our
  wrong-state gate becomes load-bearing.
- Category labels are noisy both ways (UC Riverside classified `investing`).
- **Volume is the real problem:** 2,766 distinct domains for Pinellas County before filtering,
  295 after. That is more crawl than 12 SERP queries produce — it trades search cost for fetch
  cost, the same trap as Option 1 but larger.

---

## 3. Comparison table

Cost is one full 5,958-geo backfill. "Coverage" is versus today's 72,090-search output.

| Option | Searches | Cost | Coverage | Effort | Risk |
|---|---:|---:|---|---|---|
| **Status quo** (SerpApi Developer) | 72,090 | **$1,081** VERIFIED | baseline | — | vendor litigation |
| 3a. SerpApi Big Data, no other change | 72,090 | **$825** VERIFIED (3 mo) | identical | 0 d (billing) | none |
| 3b. DataForSEO Standard, templates unchanged | 72,090 | **$172** VERIFIED | parity ESTIMATE | 3–5 d (async) | untested parity |
| 3c. Serper, templates unchanged | 72,090 | **$100** ESTIMATE | parity ESTIMATE | 1 d | outages, no SLA |
| **1. Registry-first** (CISA + Scorecard) | 18,369 | **$276** SerpApi / **$11** DFS | −26% city `.gov`; `.org` unchanged | 1–2 d | fetch-cost transfer |
| **2. + county→city inheritance** | 7,083 | **$106** SerpApi / **$50** DFS/Serper | −~5% ESTIMATE (n=1) | +1 d | dedupe ×N geos |
| 4. IRS BMF + 990 | 0 (supplement) | **$0** VERIFIED | +`.org`; misses boards/coalitions | 4–6 d | mailing-address mis-file |
| 5. Overture Places | 0 (supplement) | **$0** VERIFIED | 10/12 finds; high junk | 2–4 d | 295 domains/geo crawl load |

---

## 4. Recommended stacks

### Stack A — "Ship Monday" (lowest risk, no vendor change)

**Registry-first + county→city inheritance, staying on SerpApi.**

```
CISA .gov registry (free, vendored)      .gov candidates      $0
College Scorecard (free, vendored)       .edu candidates      $0
authority_filter unrestricted queries    .org/.com          7,083 searches
county→city inheritance                  3,762 city geos      $0
                                                    -----------------
7,083 × $0.015 (SerpApi Developer)                        $106.24
```

**Total: ~$106 VERIFIED arithmetic** (unit price VERIFIED; 7,083 derived from HEAD templates).
Two Developer months, or one Production month at $150 with headroom.

**What it gives up:** ~26% of cities lose their own city-hall `.gov` row (VERIFIED n=1 county);
~5% of city-specific `.org`/`.com` (ESTIMATE n=1 city); amplified same-org-×-N-geos duplication.
**What it keeps:** the current vendor, the current legal posture, the current cost rails, and
every downstream gate. **90% saving with zero vendor risk and ~2 days of work.**

### Stack B — "Recommended" (Stack A + a verified-cheaper vendor)

```
Stack A candidate sourcing                                7,083 searches
DataForSEO Live mode (synchronous, NO operators remain)   7,083 × $0.002 = $14.17
                                     → $50 minimum deposit applies
```

**Total: ~$50 (deposit float; $14 consumed)** — VERIFIED unit price, VERIFIED that the 5x
operator multiplier **no longer applies** because Option 1 deletes every `site:` query. This is
the elegant part: the registry swap that saves the searches also removes the multiplier that
made DataForSEO unattractive. Live mode keeps the synchronous client, so no async rewrite.

**What it gives up:** everything Stack A gives up, plus an unproven result-parity assumption and
a second vendor relationship. **~95% saving.**

### Stack C — "Maximum coverage, still cheap"

```
Stack B                                                              ~$50
+ IRS BMF + 990 website index (free nonprofit registry)              $0
+ keep city-level authority queries (no inheritance) 18,369 × $0.002 $36.74
                                                              ------------
```

**Total: ~$87 ESTIMATE.** Buys back the city-specific `.org`/`.com` that inheritance discards
and adds the nonprofit long tail. **Costs 4–6 extra engineering days** and raises fetch load
materially. Do this only if Stack B's validation shows unacceptable city-level recall.

---

## 5. The honest recommendation

**Adopt Stack A. Do not sign anything, and do not write a line of vendor-swap code, until the
free validation below passes.**

The reasoning:

1. **The lever is search *volume*, not search *price*.** 74.5% of the bill buys answers two free
   registries already hold. Vendor arbitrage alone (Option 3) saves 24–91% while leaving the
   structural waste in place; removing the waste saves 90% while keeping the vendor.
2. **Stack A is reversible.** It changes what enters the funnel, not who we buy from, not the
   legal posture, not the cost rails. If validation fails, revert a merge in `discover.py`.
3. **The vendor swap is a second, independent decision** worth ~$56 more. Take it after Stack A
   is proven, not at the same time — do not confound two changes in one measurement.

**Say the uncomfortable part plainly: coverage genuinely costs money at the margin.** Stack A is
not free of quality loss. It measurably drops ~26% of city-hall `.gov` rows and an estimated ~5%
of city-specific orgs, and the two hardest-to-find org classes the client explicitly values —
state licensing boards (`ncsappb.org`) and unincorporated coalitions
(`northalabamamentalhealthcoalition.org`) — are absent from **every free dataset investigated**.
They are reachable only by paid unrestricted search. Anyone promising $0 and full coverage is
wrong. The defensible claim is **"~90–95% of the cost removed for a single-digit percentage of
recall, measured before we commit"** — and if the client wants that last slice, it costs the
difference between Stack B and Stack C.

### What to validate cheaply first — do this before anything else

Three experiments. **The first costs $0 and is the one that matters.**

**Experiment 1 — recall replay against the live production dataset. Cost: $0. Time: half a day.**

We have a 589-row production dataset over 70 geos, and 343 cached SERPs in `data/cache/serpapi/`.
Do **not** run new searches. Instead:

1. For each of the 70 geos in the live dataset, generate the Stack A candidate set offline:
   `registry.domains_for_geo(...)` + Scorecard `.edu` + the **cached** authority-query SERPs,
   with city geos reading their **county's** cached results.
2. Compute: **what fraction of the 589 already-accepted prospects does that candidate set still
   contain?**
3. Break the answer down by level (state/county/city) and by trust band (the 71 high-trust rows
   matter more than the 381 low).

**Kill criteria, agreed before running:** if overall recall < 90%, or high-trust recall < 95%,
Stack A is dead as specified and Stack C's extra sources become mandatory. This directly tests
both the CISA 38%-hit worry and the county→city inheritance assumption on **real accepted
output**, not on candidate counts — which is exactly the metric that made the previous two
estimates collapse.

**Experiment 2 — county→city loss on n≫1. Cost: $0. Time: 2 hours.**

The ~5% loss figure is n=1 (Clearwater). Re-run the scope classification over every
city/county pair already in the cached corpus, and deliberately include a Virginia independent
city and a city-county (San Francisco or Denver) as adversarial cases. If loss exceeds ~15% on
that sample, restrict inheritance to counties with >3 cities and search the rest.

**Experiment 3 — vendor parity A/B. Cost: ~$0.12. Time: half a day.**

Only if Experiments 1–2 pass. Take 20 geos already in the dataset, run the **operator-free**
authority templates against DataForSEO Live (`20 × 3 = 60 queries × $0.002 = $0.12`) and diff
the candidate-domain sets against our cached SerpApi results for the same geos. Require ≥95%
overlap on surviving candidates before migrating. **No stream ran a single live query against
any alternative provider — this gap must be closed with money, and $0.12 closes it.**

Total validation cost: **twelve cents.** There is no excuse for committing before it is done.

---

## 6. Ruled out

Recorded so nobody re-derives them.

| Rejected | Reason |
|---|---|
| **Cutting queries per geo** | **REFUTED on our own cached data.** Only 25/127 candidates (19.7%) are surfaced by more than one query variant — 80% come from exactly one query, so cutting queries cuts candidates almost proportionally. Even with *optimal* greedy set-cover ordering, 5 queries retain only 72.9%. No saturation cliff exists within 10 queries. Halving queries buys a ~27% quality cut, not a free lunch. |
| **Bing Search API** | **RETIRED** 2025-08-11 (Microsoft Lifecycle). Replacement "Grounding with Bing Search" is $35/1,000 — 2.3× the bill we are trying to cut, and it returns grounded answers, not SERPs. |
| **Google Custom Search JSON API** | **CLOSED to new customers**, shutdown by 2027-01-01. Also $5/1K, a hard 10,000/day cap, and it searches a configured engine, not the open web. |
| **Google Places API (New)** | `websiteUri` is an **Enterprise-tier field**, and billing takes the highest tier requested → $35/1,000. ~$834/run for *worse* data: state boards and coalitions are not consumer POIs. |
| **Yelp Fusion** | $7.99–14.99/1,000 for a consumer-review index that covers civic and association sites worst. |
| **Brave Search API** | $5/1,000 (8× DataForSEO) on a thinner independent index, and Brave's own forum documents that **multiple `site:` operators with `OR` return results only from the first** — our templates use exactly that syntax. |
| **Exa / Tavily** | $7–8/1,000 (7–8× Serper) with no `site:` semantics and unverified `.gov`/`.edu` recall. Exa's $20 free credit makes it a cheap curiosity, not a discovery path. |
| **ScraperAPI** | 25 credits per SERP = ~$12.25/1,000 effective — *more* than SerpApi Big Data, for a worse product. |
| **Self-hosted proxies + headless browsers** | **Costed and inverted.** ~6.4–12.8 GB/run of residential bandwidth = $14–67/run (IPRoyal/Webshare pricing pages VERIFIED), plus $4–16 of CAPTCHA solving — *more than a managed API* before a single engineering hour. Third-party estimate: ~$11,500 over 6 months to build production-grade. |
| **Bright Data / Oxylabs enterprise tiers** | Break even only above ~400,000 queries/month. Our entire universe is 72,090, once. Committing $499–999/month is a guaranteed 10–20× overspend. (Their entry/PAYG tiers remain viable and are covered under Option 3.) |
| **ProPublica Nonprofit Explorer API** | **No website field** — VERIFIED by live call; the org object has 14 keys, none website-like. A free wrapper over the same BMF, offering strictly less than the bulk file plus a rate limit. Its `ntee[id]` filter accepts only broad categories, so it cannot express F20 targeting. |
| **USAspending / SAM.gov** | **No website field** — VERIFIED by live POST. Targets by funding relationship, not org type or service geography. |
| **Wikidata** | **Wrong entity type** — a Pinellas County query returned city governments and a college, not local nonprofits. Notability bar excludes county coalitions and NAMI chapters. Broad query timed out. |
| **SAMHSA / findtreatment.gov bulk** | No bulk download (all three data.gov resources are HTML), 3 years stale, export endpoints reject requests — **and both domains are on our competitor list**. The records are treatment facilities, not associations. |
| **NAMI affiliate directory scraping** | All endpoints 403 behind Cloudflare. Circumventable with Playwright but these are private directories with no commercial-use grant — legal exposure a $1,081 bill does not justify. **NAMI chapters are well covered by IRS BMF anyway** (28 in NC, 21 in FL). |
| **Candid / GuideStar API** | **Uncostable** — no published pricing, and their docs do not confirm a website field exists. Worth a 15-minute sales call, nothing more. |
| **Common Crawl mining** | The index holds URLs, not page text; geography lives in content (~100 TB/crawl) → ESTIMATE ~$500/scan in Athena charges alone, recurring, for low precision. |
| **`num=100` / more results per search** | **Dead.** Google removed `num` in Sept 2025; SerpApi's Light Fast workaround was restricted to 3 organic results and discontinued. All 343 cached SERPs average 9.66 results. No 10×-per-credit lever exists from any Google-backed provider. |
| **Pagination as a cheaper second query** | SerpApi bills per request regardless of payload, so page 2 costs the same as a fresh variant — and since variants are ~80% orthogonal, a new variant returns more new domains. |
| **Better cache keys / cross-site dedupe** | Already optimal. MHD and AH generate byte-identical queries for the same geo, so the existing sha256 param cache already collapses them for free. |
| **State→city reuse** | Already measured and rejected by the team. Retained here as the reason Option 2 is restricted to the **county** level. |

---

## 7. Open questions

Ordered by how much they could change the decision.

1. **Does Stack A actually retain the accepted prospects?** Nobody measured recall against the
   589-row output — every coverage number in the research is a *candidate* count, and candidates
   are not published rows. **Resolve with Experiment 1, $0.** This is the question that killed
   the last two estimates.
2. **Do alternative vendors return equivalent results for our queries?** Zero live queries were
   run against any alternative provider by any stream. **Resolve with Experiment 3, $0.12.**
3. **How much fetch cost does registry-first add?** Every free source trades search cost for
   crawl cost (295 Overture domains/geo; CISA returning all state-level rows). The fetch budget,
   not the search budget, may become the binding constraint. **Resolve by counting
   candidates-per-geo before and after on the 5 cached geos, $0.**
4. **What is the true county→city loss nationally?** n=1. **Experiment 2, $0.**
5. **What does a full-year IRS 990 index actually yield?** The 54%-of-counties figure comes from
   a 4-month index sampled in the *low* filing season; 80–90% is an extrapolation. **Resolve by
   building the full-year index — ~3 GB and a few CPU-hours, $0.**
6. **Corpus size discrepancy.** The brief says 5,958 geos (99/2,097/3,762); a live sitemap fetch
   returned 5,962 MHD pages (55/2,118/3,789). The 99 vs 55 state gap is presumably MHD+AH
   double-counting. Immaterial to the ranking (<0.1%), but the final invoice depends on it.
   **Resolve by counting both sitemaps, $0.**
7. **Serper's real pricing.** Their pricing page 404s; all figures are third-party. **Resolve
   in-dashboard before purchase.**
8. **Bright Data's real rate.** Two sources disagree 2.3× ($1.50 vs $3.50/1K) and one reports a
   $500–1,000/mo minimum. Unresolvable without contacting sales; not on the critical path.
9. **Litigation trajectory.** Google's DMCA claims against SerpApi were dismissed 2026-07-20 but
   Google is amending. No theory in the complaint reaches a downstream *purchaser*, but the
   category's continuity is a live risk. **Mitigation is architectural** — keep the client behind
   a swappable interface, which every stack above preserves.
