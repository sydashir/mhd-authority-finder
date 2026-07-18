# Sheet data-quality audit — the real 622 (Session 24)

Diagnosis of the live production deliverable (`data/output/production-s21.csv` /
Postgres run #8 / master Sheet — 622 rows, 72 geos) before it goes in front of the
client. Evidence first: every defect bucketed with counts + named examples, so the
fixes are driven by what's actually in the data, not by assumption. **0 billed** —
all analysis is over the cached corpus + the persisted rows.

## Headline

622 rows. Contact-trust today: **high 77 / medium 146 / low 399**. The deliverable
is geo-sorted, so the 77 high-trust rows are scattered alphabetically and the client
opens on Alabama's weak rows. Four content defects reach real rows; two are cosmetic
/ operational.

## Buckets

### A — `.edu` whose real state contradicts the geo → 31 rows (HARD REJECT)

The ADR-020 wrong-state gate deliberately deferred `.edu` (a bare `.edu` domain
doesn't encode its state). It's now the single largest content defect: **31 rows**
where the university's real state ≠ the geo it's filed under — **6 high**, 5 medium,
20 low.

Resolved against the federal **College Scorecard** institution file (domain → state,
90% corpus coverage; 3,628 `.edu` domains vendored). Multi-campus universities map to
a *set* of states (e.g. `midwestern.edu` → {AZ, IL}, `touro.edu` → {NY, NV}) so a row
is only wrong-state when the geo is in *none* of the domain's campus states — that
alone saved 4 legitimate multi-campus rows from a false reject.

High-trust rows this removes (all genuine wrong-state):
`dsu.edu` (SD) under North Dakota, `tamiu.edu` (TX) under Hawaii, `iup.edu` (Indiana
University *of Pennsylvania*) under Indiana, `monmouth.edu` (NJ) under Port Hueneme CA,
`delval.edu` / `neumann.edu` (both PA) under Delaware. Plus `vaughn.edu` (NY) under
Alaska, `cornell.edu` (NY) under HI/NH/WY, `utah.edu`/`memphis.edu`/`syracuse.edu`/
`washu.edu`/`missouri.edu` mis-filed under California geos.

29 of 302 corpus `.edu` domains are not in Scorecard (mostly CA community-college
*district* offices — `nocccd.edu`, `socccd.edu`, `vcccd.edu` — and university-system
HQs — `ucop.edu`, `universityofcalifornia.edu`; plus `cuanschutz.edu`, the S20
residual). These fall back to the existing page-text rule honestly — flagged/low, not
asserted.

### B — phone whose area code contradicts the geo's state → 38 rows

Phones encode geography (NANP), and 38 rows carry a phone whose area code maps to a
different state than the geo. Resolved via the `phonenumbers` geocoder (the maintained
libphonenumber dataset — authoritative, already a dependency, better than a
hand-typed area-code table). Toll-free (800/888/877/866/855/844/833) → no geography →
neutral (kept, not trust-boosted); 76 rows are toll-free.

Split: **17** of the 38 are on rows bucket A already removes (moot). **21 are
phone-only fixes on surviving, in-state rows** — the org is correct but the scraped
body-text phone belongs to a third party or an out-of-state branch:
`akleg.gov` carrying **+1-559-…** (559 = Fresno CA on the Alaska Legislature),
`children.wi.gov` carrying a 313 (Detroit MI) number, `marymountcalifornia.edu` (CA)
with a 404 (Atlanta) number, `ozarks.edu` (AR, high-trust) with a 505 (NM) number.
Fix: drop the phone on a confirmed contradiction; the row and its email survive.

### C — junk page types promoted → 12 rows (2 high, 10 medium)

Press releases, news posts, event pages, and business directories scored above `low`
— they are never the "department / resource page" we want. The existing news signal
(`-3.0` weight + dated-path / title markers) fires too weakly and misses real
patterns:

- `news.calstatela.edu/2026/04/06/…` (grant press release) → **high**
- `www.tntech.edu/…/articles/mental-health-resources-…` → **high**
- `news.uci.edu`, `news.delaware.gov`, `newsroom.ucla.edu`, `news.cuanschutz.edu`
  (news subdomains); `sd34.senate.ca.gov/event/…`; `brhdut.gov/news-release/`;
  `nhbp-nsn.gov/media/…`; `scuhs.edu/news-and-events/…` → **medium**
- `hooveralabama.gov/BusinessDirectoryII.aspx` (already low — correctly)

Fix: recognise the real patterns (`news.`/`newsroom.` host; `/news/`, `/news-release/`,
`/press…`, `/media/`, `/event(s)/`, `/article(s)/`, `businessdirectory`, `/calendar`
path segments) and **cap** such a page to `low` — a junk *page type* can never be high,
same shape as the existing topic-relevance cap.

### D — third-party contact on the page → not a new defect

61 rows carry an off-domain `mailto` — all **already low** (the S8/S9 attribution
work). No high/medium off-domain contact leaks. The residual is the *in-state*
third-party phone (e.g. `uwa.edu`'s page lists the "Crisis Center of Central Alabama"
number, 205 = correct state) — area code can't catch it and it's already low-trust.
Documented as a known limit; no code change.

### E — population blank where it should resolve → 74 blank (root cause: expired key)

Not a matching bug (`STATE_FIPS` covers every state; the state lookup is a direct FIPS
call) and — corrected after live probing — **not** the run-crash I first assumed. The
real cause is an **expired `CENSUS_API_KEY`**: the live Census API now returns a 200
HTML "Invalid Key" page for every fresh lookup, which the client's `resp.json()`
swallows as a silent `not_found`. The 8 whole states blank today (FIPS
01/04/32/40/41/45/46/50 = Alabama, Arizona, Nevada, Oklahoma, Oregon, South Carolina,
South Dakota, Vermont — 50 rows) are exactly the ones that were *not* already on disk
from Session 12, when the key still worked; the cached states still resolve. The other
24 blanks are city/neighbourhood geos honestly absent from Census (e.g. Palos Verdes) —
correct `not_found`.

Two fixes: a **code fix** so an invalid-key / non-JSON response fails loudly (a logged
warning + a clear result note) instead of degrading silently; and an **operational**
one — a valid free key is needed to fill the 8 states (the code is proven correct by
every state that resolves from cache). Without a key the rows stay honestly blank; we
never fabricate a population.

### F — minor: national domain leak → 2 rows

`irs.gov` appears twice (a federal national domain, not a local authority). Add it to
`FEDERAL_DOMAINS` so it's pre-filtered. No other federal-list domain leaked.

### Cross-cutting — sort

At 68 rows / 5 geos the geo-first sort was fine; at 622 / 72 it buries the value.
Re-sort **contact-trust (high → low) first**, then population desc, then geo, so the
71 surviving high-trust rows sit at the top of what Jake opens.

## Projected effect

| | rows | high | medium | low |
|---|---|---|---|---|
| now | 622 | 77 | 146 | 399 |
| after A removal | 591 | 71 | 141 | 379 |

Plus: bucket C demotes 12 rows toward low; bucket B strips 21 misleading phones;
bucket E fills ~50 populations; re-sort floats the high rows to the top. Precision
over recall throughout — hard-reject only on a confirmed contradiction, flag/keep the
unconfirmable.

## Fixes (by bucket, by severity)

1. **A** — vendor College Scorecard `domain → state-set`; hard-reject wrong-state
   `.edu` in the scorer (Step 4).
2. **B** — `phonenumbers` area-code → state; drop a contradicting phone (Step 3).
3. **C** — strengthen junk detection + cap to low (Step 5).
4. **E** — re-run fills the 8 missing state caches (Step 6, free).
5. **F** — add `irs.gov` to `FEDERAL_DOMAINS`.
6. **Sort** — trust-first ordering + a High-Trust view (Step 2).
