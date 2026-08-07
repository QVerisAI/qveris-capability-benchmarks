# Question Lifecycle and Evaluation Model

**Status:** Contract
**Date:** 2026-08-07

## Purpose

This document defines two contracts for the benchmark platform: where benchmark
questions come from, and how a question is evaluated. It exists so that every
question in the bank answers two questions the same way:

1. Which developer selection decision does this question inform?
2. Under what objective rule is it judged completed, failed, or blocked?

It follows the product strategy: a Financial Task is the product unit and a CAP is
the measurement unit. A question always measures exactly one CAP. There is no
provider total score, no Agent-friendly composite, and no cross-CAP outcome merge.

## Question provenance

### Accepted origins

Question ideas may come from any of the recorded `SourceType` values: public
benchmarks, external task repositories, sanitized customer questions, developer
queries, provider submissions, search demand, or QVeris-authored research. Origin
does not determine priority.

The provenance rules are:

- External material is inspiration and citation only. Every source is recorded in
  `question_bank/sources.yaml` with a public URL, an authority tier
  (`official_api`, `official_market_source`, or `external_benchmark`), and a
  `citation_only` reproduction policy.
- Repository-backed benchmark sources pin an immutable commit and source task or
  artifact identifiers. A benchmark cannot be the sole authoritative truth source
  for a P0 evaluation contract.
- Every question declares `text_origin: qveris_curated`. External task text is
  never copied; the bank only records the idea and the citation.
- Sanitized customer questions use an internal reference that exposes no customer,
  contact, credential, or proprietary payload.

### Question bank entry

A question enters `question_bank/questions.yaml` only when it is:

- atomic: exactly one `cap_id`, one role, explicit input, required observations,
  completion conditions, and a selection rationale;
- reviewed: `review_status: approved`;
- attached to an exact `(scenario_id, version)` when it serves a scenario;
- contractual for P0 scenario requirements: market, language, as-of semantics,
  authoritative reference rule, tolerance rule, interface expectations, and a
  developer-selection implication.

The lifecycle boundary is enforced by `capabilities.yaml`. `candidate` means the
CAP has questions but no executable CAP Pack; `runnable` means the CAP has a
compilable `cap_packs/<cap>/cap.yaml`. A candidate question is never treated as a
provider benchmark result.

### Promotion to executable measurement

Promotion is not copying the question into another system. A runnable CAP Pack
freezes the case input and expected observations in `cases.yaml`, binds a qualified
Provider and Access Path, and defines CAP-owned response extraction and rules. The
question remains the measurement candidate; the CAP Pack makes it executable.

## Evaluation model

### Scoring unit

The scoring unit is the run cell: `(case, provider, access_path, mode, round)`.
Every included applicable cell runs Direct Test; an eligible cell runs the Agent
Trial with exactly one suite-frozen canonical tool. A cell never mixes providers,
paths, modes, or CAPs.

### Pass criteria

A question is judged by its completion conditions and evaluation contract:

- `completion_conditions` must all appear in the extracted facts. Any missing
  condition makes the outcome `partial` with the unmet conditions recorded.
- P0 evaluation contracts carry `tolerance_rule` and `reference_rule`. Numeric,
  freshness, and semantic tolerances are executable: the reference value and
  timestamp are captured at execution time from the disclosed authoritative source
  and compared per round.
- Boundary and negative-control questions require a machine-readable negative
  state (`validation_error`, `no-data`, or equivalent). Fabricated values are
  forbidden and always fail the question.

### Cell states and failure attribution

A cell ends in one of: `completed`, `provider_negative`, `infra_blocked`,
`not_applicable`, or `excluded`.

- `completed`: the pass criteria above are met.
- `provider_negative`: the interface itself rejected the request or returned an
  explicit negative state, so the provider cell fails on capability evidence.
- `infra_blocked`: credentials, environment, or benchmark-side failure prevented
  the run. This is infrastructure evidence and never becomes a provider capability
  conclusion.
- Failure reasons use the `FailureAttribution` taxonomy: invalid parameters,
  provider validation or runtime error, auth or entitlement, rate limit, network or
  timeout, empty or partial data, truncation without pagination, response
  interpretation error, Agent output error, benchmark system error, or unknown.

### Direct Test

Direct Test is mandatory for every included applicable cell and repeats at least
three rounds. Rounds support latency, reliability, and stability observations.
The reference value is captured once per round so tolerance comparison has its own
immutable evidence digest.

### Agent Trial

The Agent Trial observes whether a fixed Agent can use one predetermined canonical
tool to construct parameters, recover from interface feedback, interpret the
response, and complete the same atomic task. It records first-call argument
validity, corrections and errors, call count, tokens, elapsed time, and the
categorical outcome. Discovery, routing, multi-tool planning, and tool selection
are outside the benchmark.

### Dimension facts

Dimension facts must carry one of three states (the release validator enforces
this state contract; a missing state is treated as `evidence_insufficient`):

- `measured`: a CAP-owned definition, a repeatable measurement, and released
  evidence exist. Examples are task completion, accuracy and precision under a
  reference rule, freshness, demonstrated coverage, and Agent-interface
  observations.
- `declared`: provider documentation or marketing claims are disclosed as such.
  Declared facts never become measured facts.
- `evidence_insufficient`: the definition or evidence is missing. It is never
  filled from Provider claims or from another scenario's questions.

Question roles map to developer selection dimensions as follows:

| Question role | Selection dimension | Where the fact is produced |
|---|---|---|
| `core_positive` | Task completion | Direct Test completion conditions |
| `boundary_negative` | Task completion, error recoverability | Negative-state cells and failure attribution |
| `coverage` | Geographic fit | Demonstrated market/exchange case with official reference |
| `freshness_precision` | Data quality | Execution-time reference capture and tolerance comparison |
| `shape_completeness` | Agent integration, response schema | Schema, empty-state, pagination, and truncation observations |
| `agent_contract` | Language fit, single-tool closure | One canonical tool, first-call validity, call/token/elapsed records |

Latency, reliability, cost, and access constraints are run-level observations and
release facts, not question-level attributes. A question defines what correct
means; the run records how fast, how stable, and how expensive.

### Scoring integrity rules

- The truth source is independent of the evaluated Provider. A Provider under test
  is never its own referee.
- Coverage and language are declared per question, never inferred from a
  scenario's market or language union.
- Evaluation rules are replayable: two builds of the same release are byte-identical
  and every fact resolves to an immutable release and evidence digest.
- Aggregate score and rating fields are rejected by the release model. A profile
  shows per-CAP, per-path tradeoffs and limitations.

## Adding a question: the checklist

Before a question is added, confirm:

1. It measures exactly one CAP with one role.
2. The role maps to a selection dimension or Agent-interface observation above.
3. It has an executable pass rule, not a placeholder. Without an authoritative
   reference and a numeric, freshness, or semantic tolerance, it stays
   `evidence_insufficient` and cannot be promoted.
4. Coverage and language claims are scoped to the concrete case (for example
   "SSE Main Board single-security sample", not "mainland-China coverage").
5. Latency, cost, and reliability are left to run observations and release facts,
   not encoded as question text.

## Related documents

- [Product strategy](product-strategy.md)
- [CAP selection and provenance policy](cap-selection-policy.md)
- [CAP question bank](question-bank.md)
- [Evidence and disclosure policy](evidence-and-disclosure-policy.md)
- [Provider qualification policy](provider-qualification-policy.md)
