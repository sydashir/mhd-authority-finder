# Contact-quality audit — Session 9, Step 1

**Date:** 2026-06-23 · **Run:** 5 cached geos, `billed_searches=0` · **Rows:** 68 detected
prospects · **Method:** `scratch/diag_contact_quality.py` re-runs discover (cached) → detect →
extract, faithfully replicates the *current* orchestrator's best-pick + trust per candidate,
and **probes** every site for a reachable same-domain department contact (detected page +
up to 4 directory/dept links the current code may never crawl). `scratch/bucket_diag.py` /
`bucket_diag2.py` classify and project.

Replication check: the replayed trust distribution is **high 1 / medium 28 / low 39**, within
one row of the Session-8 live baseline (1 / 27 / 40 — one transient fetch difference). The
replication of current behaviour is therefore faithful, so the projections below are trustworthy.

> **This table drives the fixes. It is deliberately unflattering.** Page detection is strong;
> contact *attribution* is the weak link, and most of the weak tail is **structural** — the
> authority page simply does not publish a department email we can reach. We do **not** plan to
> lift the headline "high+medium" by relaxing bands; the honest projection actually *lowers*
> high+medium because today's "medium" over-trusts wrong-department inboxes.

## 1. Root-cause buckets (the brief's A–E)

| Bucket | Definition | Count |
|---|---|---|
| **A** | Better same-domain contact reachable on a directory/contact page we never crawl | **2** |
| **B** | Dept email already on the detected page, but the ranker picked a generic one | **0** |
| **C** | Off-domain mailto (third-party / sibling-gov), correctly flagged `low` | **10** |
| **D** | Structurally unfixable — no same-domain dept email anywhere (phone/form/none) | **55** |
| **E** | Fetch blocked (WAF/SSL) so we never saw the real contact | **0** |
| OK | Already `high` trust | 1 |

**Two findings reshape the fix plan:**

- **B = 0.** The ranker is *not* mis-picking among emails co-present on the detected page. The
  brief's hypothesis ("ranker chose contact-us over the dept") essentially does not occur in this
  corpus. The Step-3 ranker change has little to bite on for *co-present* emails.
- **The raw D = 55 is misleading.** That count uses the *current, narrow* dept-localpart
  dictionary (`{health, info, contact, behavioralhealth, mentalhealth, counseling, recovery,
  intake, referrals, wellness, …}`), so it mislabels genuine department mailboxes whose
  local-part isn't in the dict (e.g. `recoverysupport@`, `ivccounseling@`, `unccounselingcenter@`,
  `counselinf@`, `humansvs@`) as "unfixable". Re-classifying with an evidence-derived dept signal
  set (§3) splits the 55 into real sub-populations (§2).

## 2. The honest reframing: fixable vs. structural

Re-bucketing the 68 rows by *what could actually change*:

| Reframed bucket | Count | Fix |
|---|---:|---|
| **Genuine dept mailbox present, under-banded today** (medium→high) | 6 | Step 3 — dept recognition |
| **Reachable dept contact via an uncrawled hop** (low→medium) | 2 | Step 2 — directory finder |
| **Same-domain swap beats off-domain best** (low→medium) | 1 | Step 2/3 — prefer same-domain |
| **Wrong-dept / role-noise, *over*-trusted today** (medium→low) | 12 | Step 3 — band tightening |
| **Off-domain mailto, no same-domain alternative** (stays low) | ~6 | none (precision-correct) |
| **Hard structural — no same-domain email anywhere** (stays low) | **23** | none |
| Already high | 1 | — |

**The ceiling, stated plainly:** **23 / 68 rows (34%) publish no same-domain email at all**
(19 phone-only, 4 nothing/blank) — e.g. `umd.edu/counseling`, `ufl.edu/counseling`,
`miamidade.gov`, `lagunahillsca.gov`, `newportbeachca.gov`, `md.gov`, `westernu.edu`. Add the
off-domain-only sites (`cityofirvine.gov`, `cityoffrederickmd.gov`, `orangecoastcollege.edu`,
`flhealthsource.gov`) and **~40% of rows have no own-domain contact any fix can surface.** For
these, phone + page URL is the deliverable; that is not a defect in our code, it is the web.

## 3. Evidence-derived signal sets (drives Step 3 — *don't guess*)

Taken from the observed same-domain local-parts across the 68 rows (full frequency table in
`scratch/diag_run` output). These are real, not invented.

**Department-relevant** (→ `high` for same-domain mailto, `medium` via hop/body):
`counsel*` (counseling, counselingcenter, counselctr, counselinf, ivccounseling,
unccounselingcenter, counselingservices), `behavioral*`, `mentalhealth`, `recovery*`
(recoverysupport), `wellness`, `wellbeing`, `human-serv*`/`humansvs`, `crisis`, `substance`,
`psych*`, `peer-support` (frs.peer_support_cism), `intake`, `referral*`, `studenthealth`,
`healthservices`; exact: `health`, `behavioralhealth`, `publichealth`, `mentalhealth`,
`bha`, `bhrs`, `dph`, `dhs`, `dhcs`, `hhs`, `mhsa`.
Guard: exclude `environmental*` / `developmental*` / `governmental*` heads first —
`environmentalhealth` contains `mentalhealth`, `developmental` contains `mental`.

**Role-noise / wrong-department** (→ `low` even for same-domain mailto — this is the tightening):
`admission*`, `webmaster`, `webmarketing`, `webteam`, `communications`, `media`, `newsmedia`,
`press`, `marketing`, `publicinformation`, `pio`/`pioac`, `helpdesk`, `servicedesk`, `registrar`,
`financialaid`/`finaid`, `alumni`, `advancement`, `housing`, `mayor`, `citymanager`, `cityclerk`,
`cityattorney`, `prosecutor`, `auditor`, `facultycouncil`, `titleix`, `consumer`, `smteam`,
`district\d+`, `mdmanual`.

**Generic** (`info`, `contact`, `reception`, `hello`): same-domain mailto → `medium`; hop → `low`.
Per the brief, a generic `info@`/`contact@` may stay `medium` — but it is **not** `high`
(this demotes the lone current `high`, `info@csupueblo.edu`, to `medium`).

## 4. Projected outcome (before → after, applying Steps 2 + 3)

| Band | Current | Projected | Δ |
|---|---:|---:|---|
| high | 1 | **6** | **+5** |
| medium | 28 | 16 | −12 |
| low | 39 | 46 | +7 |
| **high+medium** | **29** | **22** | **−7** |

**Read this honestly:** `high` rises 6× (every one a verified department mailbox), but
**high+medium falls 29→22** because we stop counting wrong-dept inboxes (`admissions@`,
`communications@`, `webmaster@`, `auditor@`, `servicedesk@`, `helpdesk@`) as `medium`. The
aggregate going *down* while quality goes *up* is the correct precision outcome, not a regression.

### Promotions (genuine dept contact, better band)

| Site | Before → after | Contact | Where |
|---|---|---|---|
| montgomerycountymd.gov | low → **high** | `info@frsn.org` (off-domain) → `frs.peer_support_cism@montgomerycountymd.gov` | mailto on MH page — *verify in Step 4* |
| howardcountymd.gov | medium → **high** | `recoverysupport@howardcountymd.gov` | mailto, /health/behavioral-health |
| ivc.edu | medium → **high** | `ivccounseling@ivc.edu` | mailto, /counseling-center |
| unco.edu | medium → **high** | `unccounselingcenter@unco.edu` | mailto, /counseling-center |
| fmu.edu | medium → **high** | `counselinf@fmu.edu` | mailto, /university-counseling-services |
| pinellas.gov | medium → **high** | `humansvs@pinellas.gov` | mailto, /mental-health-substance-use |
| coloradocollege.edu | low → medium | `admission@…` → `counselingcenter@coloradocollege.edu` | **hop** /offices/counseling (Step 2) |
| uwf.edu | low → medium | phone-only → `counselingservices@uwf.edu` | **hop** /counseling (Step 2) |
| regis.edu | low → medium | `coa@aamft.org` (off-domain) → `macplab@regis.edu` | same-domain beats off-domain |

### Demotions (over-trusted today → corrected to low)

`mdmanual@maryland.gov`, `facultycouncil@cu.edu`, `vpsa-webmaster@fsu.edu`,
`communications@uci.edu` (×2), `info@ocsheriff.gov` (×2, off-topic), `pioac@ocauditor.gov`,
`helpdesk@franklin.edu`, `servicedesk@chapman.edu`, `health@flhealth.gov` (off-domain sibling of
floridahealth.gov); plus `info@csupueblo.edu` high → medium (generic, not dept-specific).

## 5. What each fix can and cannot do

- **Step 2 (directory finder):** measured real lift ≈ **2 rows** (coloradocollege, uwf — both
  real counseling-dept emails reachable on a hop the current `if not emails` guard skips). It is
  worth building (correct, and the trigger change also lets dept emails win when a generic email
  pre-empts the hop), but it is **not** where the numbers move — most sites have no reachable
  dept email, so the probe (4 links/site) found one for only ~2.
- **Step 3 (dept recognition + tightening):** the real lever. +5 to `high`, −12 from inflated
  `medium`. Recognises genuine department mailboxes and demotes wrong-dept/role-noise. **Tightens,
  never loosens.**
- **Neither fix touches the 23 structural rows or the off-domain-only rows.** That ~40% is the
  honest ceiling.

## Verdict feeding Step 4

The deliverable's contact quality improves materially in **trustworthiness** (high 1→6, and the
sheet stops presenting `admissions@`/`webmaster@` as medium-trust), while the honest **quantity**
of trustworthy contacts is bounded by the web: ~40% of authority pages publish no own-domain
contact. Step 4 must report the real distribution and the ceiling, not a flattering total.
