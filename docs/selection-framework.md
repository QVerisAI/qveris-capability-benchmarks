# Benchmark Selection Framework

**Status:** Contract
**Date:** 2026-08-09

This document fixes the four selection decisions that drive every benchmark
release and comparison article: which CAP, which questions, which suppliers,
and which dimensions. It also fixes the evidence rule that Harbor assessments
are reference only, never the basis for our published conclusions.

## 1. CAP selection

The CAP universe comes from the Harbor explore catalog (the canonical CAP
contract registry). Selection filters:

1. Evaluability: `coverage: full` and `provider_count >= 3` (57 CAPs today).
2. Buyer value: the CAP answers a real developer selection query (quote,
   reference, news, fundamentals first; then the rest by provider count).
3. Batch order: high-value CAPs first; each batch runs the full loop
   (question bank → Direct Test → Agent probes → release facts → article)
   before the next batch starts.

## 2. Question selection

Questions are contract-derived, not hand-written from scratch:

- `standard_query.required` → question input.
- `field_spec.required` → required observations.
- Tool namespace coverage (`claimed_namespaces` minus SV-probed
  `unsupported_namespaces`, resolved through the SNS registry) → market
  coverage question. Harbor's `scope.market_hint` and `claimed_markets` are
  both deprecated; registry market tags are only a legacy projection and must
  not be presented as verified coverage. Where namespace SV has not run for a
  CAP (e.g. MKT.DIVIDENDS), record coverage as pending or run our own
  per-namespace probes. `history_scope` → freshness question;
  `row_key`/`output_cardinality` → shape/no-data question.
- Every CAP needs `core_positive` + `boundary_negative`; other roles are added
  only when the contract supports them.
- Boundary questions exercise the contract's explicit negative states
  (invalid identifier, missing one-of-required, unsupported market).

Question role maps to dimension family: core_positive → accuracy/completeness,
boundary_negative → error recovery, coverage → market coverage,
freshness_precision → freshness/precision, shape/no-data → data shape,
agent contract → AI parameter fill and response interpretation.

## 3. Supplier selection

The Harbor coverage snapshot provides the supplier *candidate set only*. A
supplier enters a release when it passes our own checks:

1. Verified QVeris provider page (`GET /rpc/v1/providers/{provider_id}` → 200).
2. Execution authorization exists (Direct Test runs through QVeris; no
   credentials = `N/A`, never a low score).
3. One row per legal entity (same-entity brands/connectors are merged).
4. A CAP comparison needs at least 3 qualified suppliers; below that, publish a
   single-supplier review instead of a comparison.

States: 合格 (all applicable cells pass), 未完全达标 (any cell fails),
未测 (no canonical tool or no authorization — not scored), N/A (not applicable).

## 4. Evaluation dimensions

Dimensions are generic operators instantiated by each CAP contract:

| Operator | Measures | Instantiated by |
|---|---|---|
| `required_field_presence` | completeness | `field_spec.required` |
| `field_type_validity` | accuracy | `field_spec` types/enums |
| `row_key_completeness` | shape | `output_cardinality` + `row_key` |
| `timestamp_freshness` | freshness | time-semantic fields |
| `market_routing` | market coverage | tool namespace coverage (`claimed_namespaces` − SV `unsupported_namespaces`, SNS registry); own per-namespace probes when SV pending |
| `language_mapping` | language coverage | language fields (only when meaningful) |
| `latency` / `reliability` / `cost` | gateway behavior | execution traces + billing |
| `agent_param_fill` | AI 入参落参 | `standard_query.required` + question |
| `agent_response_interpretation` | AI 出参解读 | question observations + response schema |
| `agent_error_recovery` | AI 错误自愈 | 冻结失败响应 + 修正后重试（见 `docs/ai-friendliness-protocol.md`） |

Market coverage for `market_routing` may reuse Harbor SV as preflight input for
representative symbols and explicit unsupported scopes. Unknown, missing, or failed
preflight results still run Direct Test. Published coverage states come only from
our own immutable release; Harbor grades are never copied into public copy.

## 5. Evidence rule: Harbor is reference only

This is a red line, not a preference:

- Harbor coverage/grades may be used to build the supplier candidate list and
  to flag anomalies for investigation.
- Every published 合格 / 未完全达标 / measured fact must come from our own
  runnable probe or release: `scripts/cap_direct_test_probe.py` (Direct Test)
  and `scripts/agent_param_fill_probe.py` +
  `agent_response_interpretation_probe.py` (Agent Trial).
- When our result differs from a Harbor snapshot (for example Alpha Vantage on
  corporate actions), our own reproducible result wins, and the difference is
  reported to Harbor as an issue for their pipeline check.
- Raw evidence stays private (`evidence/private/`); public copy cites only
  sanitized, digest-bound observations with the test date.

## 6. Harbor collaboration flow

1. Our probe finds a result that differs from a Harbor snapshot.
2. Open a Harbor issue with our evidence (run IDs, DB records, repro commands).
3. Track the issue; do not block our release on its resolution.
4. When Harbor re-evaluates, re-run our probe and reconcile in the next edition.

## 7. Retest policy

Every edition refreshes: Direct Test (fixed cases, ≥2 rounds per applicable
cell), AI param-fill (2 rounds per tool), and response interpretation (2 rounds
per tool) on the same date. A normal unchanged-contract retest targets 2–4
hours; contract or credential changes reset the affected cells only.
