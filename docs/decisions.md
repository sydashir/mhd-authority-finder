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
