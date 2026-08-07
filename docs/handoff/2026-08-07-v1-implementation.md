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
- PR #33 merged the CAP layout clarification: configuration remains at
  `cap_packs/`, CAP-specific extractors live under
  `src/qveris_bench/cap_packs/`, and the smoke pack is consistently named
  `stock_quote_smoke`.

## Important remaining gaps

### ETF Holdings formal CAP

The release is structurally valid and has Direct evidence for the two included
paths, but it does **not** yet meet the design's full 5–8-provider formal CAP
cohort: six candidates are qualified in the registry, while only Alpha Vantage
and FIU are currently included/executed. Do not describe this as fully complete
against the original cohort acceptance criterion.

### Task 13: Stock Quote smoke CAP

The repository contains a configuration-only smoke pack under
`cap_packs/stock_quote_smoke/`, with one Finnhub direct binding and one round. It
is not the planned completed smoke benchmark. The next implementation must freeze
an attributable two-provider cohort, include valid market cases as applicable and
a negative control, run two Direct rounds, preserve raw/sanitized evidence
separation, and generate a release without adding a score. A prior QVeris search
only inspected tools; it did not execute a provider and is not benchmark evidence.

### Task 14: native MCP Direct E2E

PR #30 (`feat/wind-native-mcp-e2e`) is still open. Its CI is green, but it is not
merged and does not yet replace the required fresh-clone, second-operator proof.
The approved Wind credential exception is narrow: use `WIND_MCP_API_KEY` only in
the `benchmark-e2e` environment for one fixed native-MCP Direct E2E; never commit,
expose, route, or reuse it for another provider.

## Current Git state

- `master`: includes PR #33 (layout and reading map).
- `feat/stock-quote-smoke-completion`: current implementation branch; use it for
  Task 13 after defining its acceptance criteria.
- `feat/wind-native-mcp-e2e`: separate worktree/PR #30; do not combine its changes
  with Task 13.

## Safe next steps

1. Re-read the Task 13 section of the design plan at `95179a8`, then define a
   measurable AC table before editing files.
2. Audit the existing Stock Quote pack, provider registry, Direct executor, and
   release gates before adding any provider binding.
3. Create/update the Task 13 PR as soon as the smallest reviewable contract change
   exists; run focused checks locally and let CI carry broad regression coverage.
4. Run the mandated Direct cells only with authorized environment secrets; record
   blocked infrastructure as `infra_blocked`, never as provider-negative.
5. Before any completion claim, verify the release digest and run a real CLI
   end-to-end compilation/execution path, then perform the required PR review.

## Baseline verification

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run qveris-bench cap list
```
