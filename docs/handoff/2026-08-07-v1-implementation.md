# Capability Benchmark Platform v1 Handoff

- **Date:** 2026-08-07
- **Design source:** `docs/capability-benchmark-plan` at `95179a8`
- **Repository:** `QVerisAI/qveris-capability-benchmarks`
- **Current base:** `master` at merge commit `b5aa1cb`

## Product boundary

This is an evidence-first, file-backed provider capability benchmark platform for
Stages 1–4 only. It compares a specific `capability × provider × access path`
under a frozen suite; it is not a provider ranking product.

- Direct Test is mandatory for every included, applicable path.
- An Agent Trial may expose exactly one suite-frozen canonical tool. It is not
  routing, discovery, or multi-tool planning.
- Native and QVeris paths are separate observations and never merge into one row.
- Outcomes are categorical and evidence-bound. Do not add a provider total,
  Agent-friendly composite, or any other score.
- Raw responses and credentials stay outside the repository. Public artifacts are
  sanitized evidence and immutable release bundles only.

Do not implement Stage 5/6 systems, external BYOK, a database, a leaderboard,
SEO/content automation, scheduled retesting, or a portal.

## Read the code in this order

1. [`docs/architecture/platform.md`](../architecture/platform.md) defines the
   contract and boundaries.
2. [`docs/architecture/repository-map.md`](../architecture/repository-map.md)
   maps a CAP from configuration to release.
3. `cap_packs/<cap>/` contains the frozen, versioned CAP inputs.
4. `src/qveris_bench/suites/` validates and expands a suite into stable run cells.
5. `src/qveris_bench/execution/` owns Direct execution, state, retries, and traces.
6. `src/qveris_bench/cap_packs/<cap>/extractors.py` owns only CAP-specific response
   interpretation; `src/qveris_bench/outcomes/` remains generic.
7. `src/qveris_bench/evidence/` and `src/qveris_bench/releases/` turn evidence into
   a gated, deterministic release.

## Completed and merged

- Tasks 1–11 established the generic Core, file-backed contracts, provider
  qualification, frozen suites, execution modes, evidence controls, and release
  machinery.
- Task 12 produced and verified the public ETF Holdings release
  `etf-holdings-2026-q3-v1`. Its release digest is
  `sha256:62df52047ecb0bcf66fce96a0240f97f29c1bc9e55066ca9e06ae0f878d00c0f`.
- Task 13 produced and verified the two-provider, two-round Stock Quote smoke
  release `stock-quote-2026-q3-v2`.
- Task 14 completed the operator handoff, clean-checkout replay, fixed Wind native
  MCP Direct E2E, CI, review, and merges. Wind uses only its single frozen
  canonical tool and publishes sanitized terminal evidence.

## Important remaining gaps

### ETF Holdings cohort and execution boundary

The US ETF cohort contains six terminally qualified candidates. Alpha Vantage and
FIU are included and have completed the frozen three-round Direct matrix. Twelve
Data, Financial Modeling Prep, Finnhub, and EODHD are explicitly excluded and
must not be executed without a new authorization and qualification decision.

### Scope guard

Stages 5 and 6, external BYOK, a database, a leaderboard/SEO system, provider
totals, and Agent-friendly composite scores remain deliberately unimplemented.

## Baseline verification

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run qveris-bench cap list
```
