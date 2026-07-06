# Wrong-state audit (Session 20, Phase F2)

Session 19 flagged ~9% of scale-test rows as wrong-state / out-of-geo — the top quality risk for the
full 64-geo run (24 of those are state-level AH geos, the exact trigger). A wrong-state row is not
"low quality", it is **wrong**: it would email a different region's org. This audit identifies the actual
cases from the S19 cached data (`data/output/s19-sample-v2.csv`, 83 rows) and buckets them so the fix is
evidence-driven.

## Why the current (text-only) check misses them

`score_page` rejects a candidate only when **another** state's full name dominates the page text (≥2
mentions) **and** the target state is completely absent. It never inspects the candidate **domain's** real
location. Two blind spots follow:

1. A wrong-state place **named after the target state** — the page legitimately features the target state's
   word, so `target_count > 0`, no rejection, and it even earns the `target_state_present` bonus.
2. An out-of-state **university** (`.edu`) — the domain carries no state, and its page may not dominate on
   any other state name, so nothing fires.

## The cases (8 of 83 ≈ 9.6%)

### Bucket 1 — domain encodes a **contradicting** state (reliably derivable → HARD REJECT)

| Candidate | Target geo | Real location | Why text-only missed it |
|---|---|---|---|
| `wyomingcountyny.gov` | Wyoming (state) | **Wyoming County, New York** | The page says "Wyoming" constantly — it's the county's name — so `target_count>0` and it got the target-state *bonus*. Only `…county**ny**.gov` reveals New York. |

This is the killer pattern and the reason a domain check is necessary: text can be actively misleading.

### Bucket 2 — out-of-state **university** (`.edu`, NOT domain-derivable → tightened text/locality → DEMOTE)

| Candidate | Target geo | Real location | Current conf |
|---|---|---|---|
| `divinemercy.edu` | Wyoming (state) | Divine Mercy Univ, **Virginia** | **high** (worst slip) |
| `cornell.edu` | Wyoming (state) | Cornell, **New York** | low |
| `cuanschutz.edu` | Palos Verdes, CA (city) | CU Anschutz, **Colorado** | medium |
| `memphis.edu` | Long Beach, CA (city) | Univ of Memphis, **Tennessee** | low |
| `franklin.edu` | Palos Verdes, CA (city) | Franklin Univ, **Ohio** | low |
| `pitt.edu` | Palos Verdes, CA (city) | Univ of Pittsburgh, **Pennsylvania** | low |

`.edu` domains carry no state, and there is no reliable public university→state map without a dataset, so
these cannot be hard-rejected honestly. They are handled by tightening the text signal: a candidate that
**cannot** confirm the target state (by domain) or locality (by text) is capped to **low / flagged**, not
shipped as verified.

### Bucket 3 — cryptic out-of-state acronym `.gov` (NOT reliably derivable → tightened text → DEMOTE)

| Candidate | Target geo | Real location | Current conf |
|---|---|---|---|
| `dconc.gov` | Fullerton, CA (city) | Durham County, **North Carolina** | low |

`dconc` (Durham County NC) is a cryptic acronym — deriving `nc` from it is not reliable (false-positive
risk), so it falls to the same tightened text/locality gate as Bucket 2.

## What is *reliably* derivable from a `.gov`/`.us` domain (and what is not)

- **Reliable — assert geography:** state-portal registrable domain / subdomain (`ny.gov`, `ca.gov`,
  `texas.gov`, …); a `county{2-letter-abbr}` suffix (`wyomingcounty**ny**.gov` → NY — the "county" anchor
  makes the abbr trustworthy, and a county domain always encodes its **own** state).
- **NOT reliable — fall back honestly:** bare `{city}{abbr}.gov` (`napa.gov` ends in `pa` = Pennsylvania — a
  false positive), full-state-name suffix (`port**washington**.gov` is in NY/WI, not WA state), any `.edu`,
  cryptic acronyms. These derive `None` and use the text/locality gate.

## Fix (drives the implementation)

1. **`candidate_state(url)`** — reliably derive a `.gov`/`.us` domain's state (portal + `county{abbr}` only),
   else `None`.
2. **Domain contradicts the target → hard reject** (`wrong_state`), regardless of page text. [Bucket 1]
3. **Geo-confirmation gate** — a candidate is *geo-confirmed* iff the domain confirms the target state, or
   the target state name appears in the page text, or (county/city) the locality name appears. A candidate
   that is **not** geo-confirmed is capped to **low** confidence / flagged. [Buckets 2–3]
4. **Precision over recall:** hard-rejection requires domain proof (never a text guess); everything
   unconfirmable is demoted, not deleted, so a legitimate-but-unconfirmable candidate is flagged for a human
   rather than silently shipped or wrongly killed. Domain-confirmed candidates (state agencies, in-state
   county domains) are explicitly **protected** from demotion.

## Risk to watch (reported honestly in Step 5)

The demotion gate can demote a **legitimate** in-state `.edu` whose page never names its state or locality
(e.g. `cornell.edu` for the New York geo — correct, but unconfirmable from domain or, possibly, text). That
is an accepted precision-over-recall cost — a demotion to low (flagged, still on the sheet), never a
rejection — and the false-positive count is measured and reported.
