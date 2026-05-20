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
