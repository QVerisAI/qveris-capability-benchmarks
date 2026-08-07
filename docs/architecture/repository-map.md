# Repository Map

This map is the shortest path for reviewing a benchmark without confusing
capability-specific rules with the reusable platform Core.

For the product-facing relationship between Financial Tasks, CAPs, and developer
selection evidence, start with `docs/product-strategy.md`.

## Read one benchmark end to end

1. Start at `cap_packs/<cap>/cap.yaml`. It defines the business capability and
   its provenance. `cases.yaml`, `observation-schema.yaml`, `outcome-rules.yaml`,
   `provider-bindings.yaml`, and `suite.yaml` freeze the benchmark inputs.
   Candidate capability questions and versioned Developer Scenarios live separately
   in `question_bank/`; they have no suite, provider bindings, or executable outcome.
2. Read `src/qveris_bench/suites/`. It validates those inputs, creates the
   fingerprint, and expands a suite into `case × provider × access path × mode ×
   round` cells.
3. Read `src/qveris_bench/providers/` and `providers/`. The former is generic
   registry and qualification code; the latter is the versioned provider/access
   path inventory.
4. Read `src/qveris_bench/execution/`. It performs Direct Tests, records ordered
   events, normalizes transport errors, and maintains resumable cell state.
   `src/qveris_bench/agents/` is separate because an Agent Trial is limited to one
   suite-frozen canonical tool.
5. Read `src/qveris_bench/cap_packs/<cap>/extractors.py`. These are the only
   domain-specific response interpreters. They turn persisted raw responses into
   comparable facts; they do not decide a provider score.
6. Read `src/qveris_bench/outcomes/`. It applies generic categorical completion
   rules and failure attribution to those facts.
7. Read `src/qveris_bench/evidence/` and `src/qveris_bench/releases/`. They
   separate private raw artifacts from authorized public evidence, then build and
   verify an immutable release under `releases/<release-id>/`.

## Directory ownership

| Directory | Owns | Must not own |
|---|---|---|
| `src/qveris_bench/models/` | Versioned domain and Developer Scenario contracts | CAP field vocabulary |
| `src/qveris_bench/catalog/` | CAP source provenance | Execution behavior |
| `src/qveris_bench/suites/` | Freeze, fingerprint, and run matrix | Provider conclusions |
| `src/qveris_bench/execution/` | Transport, retries, state, trace capture | ETF, quote, or other domain semantics |
| `src/qveris_bench/cap_packs/` | CAP-specific extractors | Shared orchestration |
| `src/qveris_bench/outcomes/` | Generic outcome evaluation and attribution | CAP response parsing |
| `src/qveris_bench/evidence/` | Evidence hashing, redaction, public index | Public ranking logic |
| `src/qveris_bench/releases/` | Deterministic build, gates, and verification | Live provider execution |
| `src/qveris_bench/profiles/` | Deterministic Task Fit Profile builder | New provider or outcome semantics |
| `profiles/` | Pinned scenario profile inputs and built manifests | Live provider execution |
| `question_bank/` | Developer Scenarios, reviewed CAP question families, and public citations | Executable benchmark inputs |

## Current CAP locations

| CAP | Versioned configuration | Domain extractors |
|---|---|---|
| ETF Holdings | `cap_packs/etf_holdings/` | `src/qveris_bench/cap_packs/etf_holdings/` |
| Stock Quote smoke | `cap_packs/stock_quote_smoke/` | `src/qveris_bench/cap_packs/stock_quote_smoke/` |
| Stock Quote production family | `cap_packs/stock_quote_family/` | `src/qveris_bench/cap_packs/stock_quote_family/` |

`evidence/` and `releases/` are committed public artifacts only. Private raw
responses and credentials are intentionally outside this repository.
