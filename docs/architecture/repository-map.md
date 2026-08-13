# Repository Map

This map is the shortest path for reviewing a benchmark without confusing
capability-specific rules with the reusable platform Core.

For the product-facing relationship between Financial Tasks, CAPs, and developer
selection evidence, start with `docs/product-strategy.md`.

## Read one benchmark end to end

1. Start at `cap_packs/<cap>/cap.yaml`. It defines the business capability and
   its provenance. `cases.yaml`, `observation-schema.yaml`, `outcome-rules.yaml`,
   `provider-bindings.yaml`, and `suite.yaml` freeze the benchmark inputs.
   Candidate capability questions live separately in `question_bank/`; they have
   no suite, provider bindings, or executable outcome.
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
5. A formal CAP adds a versioned CAP-owned adapter for domain-specific response
   interpretation. It turns persisted raw responses into comparable facts; it
   does not decide a provider score.
6. Read `src/qveris_bench/outcomes/`. It applies generic categorical completion
   rules and failure attribution to those facts.
7. Read `src/qveris_bench/evidence/` and `src/qveris_bench/releases/`. They
   separate private raw artifacts from authorized public evidence, then build and
   verify an immutable release under `releases/<release-id>/`.

## Directory ownership

| Directory | Owns | Must not own |
|---|---|---|
| `src/qveris_bench/models/` | Versioned generic contracts | CAP field vocabulary |
| `src/qveris_bench/catalog/` | CAP source provenance | Execution behavior |
| `src/qveris_bench/suites/` | Freeze, fingerprint, and run matrix | Provider conclusions |
| `src/qveris_bench/execution/` | Transport, retries, state, trace capture | ETF, quote, or other domain semantics |
| `src/qveris_bench/outcomes/` | Generic outcome evaluation and attribution | CAP response parsing |
| `src/qveris_bench/evidence/` | Evidence hashing, redaction, public index | Public ranking logic |
| `src/qveris_bench/releases/` | Deterministic build, gates, and verification | Live provider execution |
| `question_bank/` | Harbor-derived CAP candidates, question families, and public citations | Executable benchmark inputs |

## Current CAP locations

The repository currently contains Harbor-derived candidates only. A formal CAP
location appears here only after its pack is verified against a private Harbor
contract export and has an immutable release.

`evidence/` and `releases/` are committed public artifacts only. Private raw
responses and credentials are intentionally outside this repository.
