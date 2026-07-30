# What actually links to a competitor directory

Ground-truth study for component 3, run 2026-07-30. The brief says:

> "Check ahrefs backlink data on this domain rehabnet.com/ to see the types of good local
> authority websites we need to fetch and get contact info for."

This is that check. It replaces the guessed query themes of sessions 27–28 with evidence.

**Method.** Ahrefs `GET /v3/site-explorer/refdomains` for three directory-type competitors —
`rehabnet.com`, `recovery.com`, `addictioncenter.com` — selecting `domain, domain_rating,
links_to_target, traffic_domain, is_spam`. 250 rows per target per sampling strategy, 3,500
units per call. Noise removed with the existing `PLATFORM_DOMAINS` blocklist,
`COMPETITOR_DOMAINS`, `FEDERAL_DOMAINS`, and Ahrefs' own `is_spam` flag.

## Sampling order is not a detail — it decides the answer

The first pull used `order_by=domain_rating:desc` and produced a result that looked
authoritative and was worthless:

| | composition | DR range |
|---|---|---|
| `domain_rating:desc` (top 250) | `nytimes.com`, `nbcnews.com`, `foxnews.com`, `amazonaws.com`, `github.io`, `secureserver.net` | 48–97 |
| `domain_rating:asc` (bottom 250) | bare IP addresses (`107.180.9.169`, `192.133.12.63`), throwaway domains | 0 |

Neither end contains a local authority organization. National media sit at the top; link-farm
residue and infrastructure sit at the bottom. **A DR-ordered sample of a backlink profile
cannot answer "what types of local organizations link here" — it answers "what is biggest"
and "what is smallest".**

The third pull filtered to the band where the brief's own example lives (`ncala.org` = DR 34):
`where domain_rating >= 5 and <= 45`, ordered by `links_to_target:desc`.

## The DR-5–45 band — 531 candidate-class domains

```
min 5 | p25 11 | median 20 | p75 30 | max 45
```

| threshold | passes |
|---|---|
| DR ≥ 40 | 42 / 531 (8%) |
| DR ≥ 30 | 137 / 531 (26%) |
| DR ≥ 25 | 212 / 531 (40%) |
| DR ≥ 20 | 268 / 531 (50%) |
| DR ≥ 15 | 340 / 531 (64%) |
| DR ≥ 10 | 421 / 531 (79%) |

**The median organization that already links to a working directory scores DR 20.** The brief's
DR 40 would discard 92% of this band. Even our provisional DR 25 discards 60% of it.

Real local organizations found in the band, with their DR:

- `agingkearney.org` (19) — aging services
- `nwcreativeaging.org` (8) — creative aging
- `employmentcounseling.org` (27)
- `theallianceofswmo.org` (30) — regional alliance, SW Missouri
- `guilfordgreenfoundation.org` (32) — county foundation
- `acirehab.org` (30)
- `rosewood-nursing.com` (21)
- `gcruralhealth.com` (7) — rural health

These are exactly the class the brief describes, and **every one of them fails DR 40.**

## Honest finding: the profile is noisier than the brief assumes

The brief's premise is that rehabnet.com's backlinks are a clean catalogue of good local
authority sites. The data does not support that.

- **150 of 681** domains in the band are flagged `is_spam` by Ahrefs and were removed.
- The largest name-cluster in the band is "recovery / addiction / sober" (66 domains), but
  inspection shows these are overwhelmingly **commercial rehab facilities**
  (`abbotsfordrehab.com`, `addictionadvocates.com`, `clearchoicerehabcenter.in`), not
  coalitions or associations. Those are competitors-adjacent, not outreach prospects.
- **421 of 531** did not match any topical name pattern at all, and the sample includes plainly
  unrelated domains (`abctales.com`, `2718281828.com`, `1buchimdreieck.de`, `12roundproductions.com`).

Name-signal clusters in the band:

| count | cluster |
|---|---|
| 66 | recovery / addiction / sober (mostly commercial facilities) |
| 14 | hospital / clinic / medical |
| 9 | mental / behavioral health |
| 7 | assisted living / senior / aging |
| 5 | association / council / coalition |
| 5 | church / ministry / community |
| 4 | foundation / charity |
| 421 | unclustered |

Incidental observation: `districtbehavioralhealth.com` — the client's own brand — appears in
`recovery.com`'s referring domains at DR 32.

## Conclusions

1. **DR is a poor gate for this source, and the backlink evidence is stronger than the earlier
   calibration.** The median real referrer is DR 20; the brief's 40 keeps 8% of them. DR should
   be a **displayed signal** on the row, not a hard filter. Type-filtering and geo-validation do
   the selection.
2. **Competitor-backlink mining is a good *calibration* instrument and a poor *targeting*
   instrument.** It settles the threshold question decisively. It does not yield clean query
   themes, because the profile is ~30% spam and heavily weighted toward commercial facilities.
3. **The strongest available signal is unused:** a domain that already links to a competitor
   directory has demonstrated willingness to list one. That is a warmer prospect than any DR
   score, and we can compute it — `link_checker` already detects competitor links per candidate
   (ADR-011). Promote that to a ranking signal rather than only a flag.
4. Query themes should stay broad (care-adjacent local organizations per the `ncala.org` /
   `dbhdduniversity.com` correction) with the platform blocklist and geo-validation doing the
   narrowing.

## Cost

6 refdomains calls × 3,500 units = 21,000 units, plus ~400 units of earlier DR work. Against a
394,000-unit monthly workspace budget this is ~5%. Cached under `data/cache/refdomains/`, so
re-analysis is free.
