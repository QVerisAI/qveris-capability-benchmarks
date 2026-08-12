# Harbor Reuse Architecture

**Status:** Accepted
**Date:** 2026-08-08

## Context

The benchmark platform needs provider symbol, dialect, namespace, and market
coverage reference data for its coverage question families. QVeris operates the
closed-source Harbor platform that already owns this data as production truth:
per-market representative tickers, provider test symbols, market anchors, and
identifier samples. Reimplementing a symbol table or dialect engine in the open
benchmark repository duplicates that operating burden.

Harbor is closed source. Its code, internal schemas, and raw data must not be
redistributed through the public benchmark repository.

## Decision

Reuse Harbor as an offline data source through a contract-level snapshot, not as a
code dependency and not as a runtime service.

- One offline export script reads a local Harbor checkout's data files and writes a
  private snapshot artifact that conforms to a benchmark-owned schema.
- The snapshot lives outside Git (`.harbor-snapshots/` is ignored). Public releases
  reference only its SHA-256 digest and sanitized aggregate counts.
- The schema and the export script are authored by the benchmark platform. They
  describe the concepts (markets, provider symbol samples, market anchors,
  identifier samples) without copying Harbor implementation or internal layout.
- Harbor data is treated as `declared` qualification input. Measured coverage
  remains the exclusive result of the benchmark's own Direct Test. A coverage
  question may reference a snapshot digest as its sample source; its referee is
  still an independent official source (SEC, SSE, Nasdaq, or equivalent).

## Responsibilities

| Owner | Owns | Does not own |
|---|---|---|
| Harbor (closed source) | Symbol/dialect/namespace/market operational truth; SV/IV verification | Benchmark conclusions, question judging, releases |
| Benchmark platform | Questions, judging rules, Direct/Agent evidence, immutable releases, profiles | Symbol table maintenance, dialect engine, market claims |
| Export script | Harbor outputs to benchmark schema conversion; private snapshot and digest | Evaluation logic |

## Snapshot contents (v1)

| Section | Source file (Harbor checkout) | Purpose |
|---|---|---|
| `markets` | `data/market-representative-tickers.yaml` | Per-market representative tickers |
| `provider_symbol_samples` | `data/audit/seed_provider_test_symbols.yaml` | Provider × market × symbol samples |
| `market_anchors` | `data/audit/market_anchors.yaml` | Anchor companies and candidate ticker variants |
| `identifier_samples` | optional operator-supplied path | Canonical identifier packages (ticker/CIK/ISIN/FIGI) |

Every snapshot carries provenance: Harbor commit, export time, export script,
input file list, and a license note marking it private operator data.

## Guardrails

- No Harbor code, internal schema, DB dump, or raw row is committed to the public
  repository. The export script only normalizes selected fields and drops internal
  notes.
- The snapshot is not a runtime dependency: benchmark runs and releases never query
  Harbor and never depend on its availability or cache state.
- Harbor conclusions may choose representative symbols or mark a scope as a
  preflight candidate. Only an explicit unsupported result or a public Access Path
  contract may create a frozen `not_applicable` cell; unknown, missing, or failed
  preflight results still require Direct Test.
- Harbor rows never become publication facts. Coverage profiles and charts consume
  the benchmark's own immutable release and sanitized terminal evidence.
- A publishable market release binds the successful workflow run, downloaded
  GitHub artifact bytes, sanitized terminal bytes, and replay manifest by digest.
  Locally regenerated attestations or terminal self-reported states are not
  sufficient provenance.
- Snapshot freshness is operator-driven: refresh when Harbor releases new symbol or
  coverage data, review the diff, and pin the new digest in the affected release.

## Operations

```bash
uv run python scripts/export_harbor_snapshot.py \
  --harbor-root /path/to/quaestio-harbor \
  --output-dir .harbor-snapshots
```

The command prints the snapshot digest. The digest, not the file, enters public
artifacts.
