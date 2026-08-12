# QVeris Capability Benchmark Platform Architecture

**Status:** Approved for v1 implementation
**Date:** 2026-08-06

## 1. Mission

QVeris Capability Benchmark Platform is open provider-selection infrastructure for
financial Agent developers. Financial Tasks organize the product around what the
developer is building; atomic CAPs provide the attributable, replayable measurement
substrate. The platform uses official provider machine interfaces to answer three
bounded questions:

1. Which provider and Access Path fit the CAPs required by a concrete financial
   Agent task under the disclosed conditions?
2. Which target selection dimensions have CAP-defined, released evidence: accuracy,
   precision, latency, reliability, cost, country/market coverage, language coverage,
   Agent-interface fitness, and access constraints? Unsupported dimensions remain
   unavailable or evidence-insufficient rather than inferred.
3. When an Agent uses one predetermined canonical tool, what parameters, errors,
   recoveries, token use, elapsed time, and final outcome are observed?

The platform does not collapse unrelated scenarios into a provider total score and
does not name a context-free "best provider." Every conclusion retains its task,
access path, environment, evidence, and limitations.

## 2. Design principles

1. Developer selection value comes before provider growth.
2. Financial Task is the product unit; CAP is the measurement unit.
3. Agent-interface fitness is a first-class set of observations, not a composite
   rating. It includes parameter clarity, response structure, error recovery,
   pagination, language mapping, and single-tool completion behavior.
4. One generic Core serves every capability; CAP Packs express domain differences.
5. The platform is greenfield. The Agent Harness is question provenance only and is
   never imported, copied as runtime code, or treated as a schema dependency.
6. Direct Test is the required source of provider capability facts.
7. Agent Trial observes one official machine interface through one predetermined
   canonical tool. It does not test discovery, routing, or long-horizon planning.
8. Agent observations remain factual. The platform records parameters, errors,
   retries, tokens, time, and categorical task outcomes without a composite rating.
9. Native and QVeris access paths run and publish separately.
10. Evidence precedes publication. Later systems consume only a formal release.
11. Git-backed files are the v1 source of truth; v1 has no database.
12. Unreliable attribution is reported as `unknown`, never reassigned to a provider.

## 3. Six-stage contract

### Stage 1: CAP selection

Inputs may include business tasks, public benchmarks, customer questions, developer
queries, provider submissions, and search demand. The output is a versioned
`CapDefinition` with a stable ID, business use, boundaries, markets, asset types,
and source provenance. An external repository source pins repository, commit, and
source task ID.

### Stage 2: Provider discovery and qualification

Candidates may include official APIs, MCP servers, OpenAPI operations, SDKs, free
tiers, sandboxes, and open-source services, whether or not QVeris already integrates
them. The output is a fixed cohort of `ProviderProfile` and `AccessPath` records,
each with a terminal inclusion or exclusion disposition and evidence.

### Stage 3: Benchmark definition and freeze

The suite freezes CAP version, cases, cohort, canonical interfaces, modes, rounds,
budgets, environment, completion rules, and disclosure rules. Compilation produces
an immutable `BenchmarkSuite`, expanded `RunPlan`, and content fingerprint.

### Stage 4: Execution, evidence, and conclusions

Every included applicable cell runs a Direct Test. Eligible access paths may also
run a constrained single-tool Agent Trial. The system stores private raw artifacts,
sanitized observations, categorical outcomes, failure attribution, and independent
digests before generating an immutable `BenchmarkRelease`.

### Stages 5 and 6: Offline consumers, not hosted services

SEO/content publication consumes `developer_selection_facts`. Provider feedback
consumes `provider_feedback_facts`. v1 may rebuild and validate a repo-local
Publication Package through a CAP-owned adapter. The generic orchestrator knows only
release references, artifact paths, adapter identity, and verification results; it
does not know CAP fields or generate editorial claims. v1 does not operate a CMS or
leaderboard, send messages, run CRM, or build a portal.

## 4. Data flow and provenance

```text
DeveloperScenario (versioned product composition; consumer layer)
  -> required CapDefinitions
TopicSource
  -> CapDefinition
  -> ProviderCandidatePool
  -> FrozenBenchmarkSuite
  -> RunPlan
  -> RawArtifact (private)
  -> ObservationFacts (sanitized)
  -> TaskOutcome
  -> BenchmarkRelease
  -> Task-fit Profile / Publication Package / Provider Feedback consumers
```

The Developer Scenario composition does not merge CAP executions or outcomes. It points
to independently released CAP facts and presents their tradeoffs in the developer's
language. It is a product information architecture, not a v1 runtime workflow.

Each layer consumes the formal product of the preceding layer. A release fact must
trace back to an observation, public evidence digest, raw digest, extractor version,
and suite fingerprint. Temporary logs cannot become release facts directly.

## 5. Domain contracts

### `CapDefinition`

Defines the capability ID, version, name, business use, scope, exclusions, markets,
asset types, and source references.

### `ProviderProfile` and `AccessPath`

A provider is an organization or product identity. An Access Path is a specific
machine interface such as `native_mcp`, `official_openapi`, `official_api`,
`official_sdk`, `benchmark_wrapper`, or `qveris_connector`. Credentials, plan,
authorization, canonical interface, and Agent eligibility belong to the Access Path.

One provider may have multiple paths. Their runs and published rows never merge.

### `BenchmarkCase`

Represents one atomic business question with inputs, negative controls, expected
observations, completion conditions, disclosure limits, and applicability. A case is
not a long-running workflow.

### `BenchmarkSuite` and `RunPlan`

The suite freezes cases, cohort, paths, modes, rounds, protocol, budget, and
environment. The Run Plan expands the suite into:

```text
case x provider x access_path x mode x round
```

Every cell receives a stable `run_key`, applicability, and state. Changes to frozen
inputs create a new fingerprint and version rather than mutating an existing run.

### `ObservationEvent` and `TaskOutcome`

Events record ordered requests, parameters, validation, provider responses, errors,
retries, token usage, elapsed time, and completion. Because the canonical tool is
fixed in advance, tool-selection fields do not exist.

Outcomes are categorical: `completed`, `partial`, `failed`, `blocked`, or
`not_applicable`. They include evidence, unmet conditions, and failure attribution,
never a provider score.

### `EvidenceBundle` and `BenchmarkRelease`

Evidence binds private raw artifacts to authorized sanitized artifacts with separate
SHA-256 digests, redaction status, disclosure policy, source-license status, and
generator version. A release can be built only when all applicable cells are
terminal and publication safety gates pass.

## 6. Core and extension boundaries

### Benchmark Core

Core owns schema validation, suite compilation, fingerprinting, matrix expansion,
credential isolation, timeouts, retries, resume, state transitions, Direct and Agent
orchestration, ordered trace capture, token and latency collection, redaction,
hashing, failure attribution contracts, and release completeness.

Core must not contain capability vocabulary such as ETF holdings, ticker, quote, or
news fields.

### CAP Pack

Each CAP Pack owns:

- `cap.yaml`: definition and provenance;
- `cases.yaml`: atomic benchmark cases;
- `observation-schema.yaml`: comparable facts;
- `outcome-rules.yaml`: categorical completion rules;
- `provider-bindings.yaml`: access paths and canonical interfaces for the CAP;
- `extractors/`: plugins that derive domain facts from raw artifacts.

Adding a CAP must not require a Core change. v1 proves this with ETF Holdings and a
Stock Quote smoke CAP.

### Provider Adapter

An adapter handles authentication, request construction, transport, raw response
persistence, and provider error normalization. It does not form editorial
conclusions, compare providers, or decide whether the business task completed.

### Observation Extractor

CAP-owned extractors derive domain facts only after the raw response is persisted and
hashed. Normalization can never replace or overwrite raw evidence.

## 7. Execution modes

### Direct Test

All included providers run Direct Tests for every applicable cell. Direct execution
measures the canonical interface's returned data, fields, coverage, pagination,
precision, freshness, latency, stability, and negative-control behavior.

### Constrained Agent Trial

A fixed Agent receives one canonical tool selected during suite freeze. The trial
records natural-language parameter mapping, first-call validity, correction and
retry, pagination or Top N interpretation, units and time handling, token usage,
elapsed time, call count, and final task outcome.

Native MCP and official OpenAPI paths are eligible by default. A benchmark wrapper
is explicitly labeled supplemental evidence and cannot represent the provider's
native Agent interface.

## 8. Run states and failure integrity

Cell states are:

- `planned`: present in the Run Plan;
- `running`: protected by a valid lease;
- `completed`: execution produced a task result;
- `provider_negative`: a valid provider response does not satisfy the task;
- `infra_blocked`: credentials, quota, network, or benchmark infrastructure blocked
  execution and the cell may be resumed;
- `not_applicable`: suite rules exclude this combination;
- `excluded`: a versioned decision and evidence digest exclude execution.

`provider_negative` is terminal evidence and cannot be retried into an infrastructure
failure. `infra_blocked` cannot become a negative provider conclusion.

Allowed failure attributions are `invalid_parameters`,
`provider_validation_error`, `provider_runtime_error`, `auth_or_entitlement`,
`rate_limited`, `network_or_timeout`, `empty_or_partial_data`,
`truncated_or_unpaged`, `response_interpretation_error`, `agent_output_error`,
`benchmark_system_error`, and `unknown`. Tool-selection and multi-tool planning
labels are outside this platform contract.

## 9. Evidence, security, and authorization

1. Secrets enter only through environment variables or a system credential provider.
2. Raw artifacts are private by default and live outside the public repository.
3. Public facts bind raw digest, public digest, extractor version, suite fingerprint,
   redaction status, and disclosure policy.
4. Redaction creates a new artifact and digest; it never reuses the raw identity.
5. When provider authorization is unclear, publication is limited to permitted
   structures, counts, field names, and statistical summaries.
6. Release gates require secret, PII, source-license, disclosure, and completeness
   checks.

## 10. v1 repository layers

```text
src/qveris_bench/
  models/       # versioned domain contracts
  catalog/      # Stage 1 CAP provenance
  providers/    # Stage 2 registry and qualification
  suites/       # Stage 3 freeze, fingerprint, and matrix
  execution/    # adapters, orchestration, state, retry, resume
  agents/       # constrained one-tool trial backend
  evidence/     # private/public stores, redaction, and digests
  outcomes/     # generic categorical evaluation and attribution
  cap_packs/    # CAP-owned domain extractors
  releases/     # deterministic release gate and bundle
cap_packs/      # versioned CAP inputs, rules, and provider bindings
providers/      # provider and access-path configuration
schemas/        # exported machine-readable contracts
evidence/       # authorized public evidence only
releases/       # immutable release bundles
```

The stack is Python 3.12, uv, Pydantic v2, Typer, httpx, the official MCP Python
SDK, OpenAI's Python SDK for the initial Agent backend, pytest, Ruff, and mypy.

## 11. v1 scope

v1 implements stages 1–4, file-backed contracts, HTTP and MCP access paths, Direct
Tests, eligible native constrained Agent Trials, an ETF Holdings CAP with a 5–8
provider candidate cohort, terminal qualification for every candidate, and at
least three Direct rounds for every included path, plus a Stock Quote smoke CAP
with two providers.
It also implements private/public evidence separation, categorical outcomes,
deterministic release bundles, safety gates, and an internal second-operator replay.

v1 does not implement SEO automation, CMS, a leaderboard website, supplier or CRM
systems, external developer BYOK, scheduled retesting, multi-Agent or multi-model
rankings, long-horizon workflows, cross-tool routing, composite Agent-friendly
ratings, or a database.

## 12. v1 acceptance boundary

The platform is acceptable when stages 1–4 execute; both CAP Packs use the same
Core; paths stay distinct; every applicable Direct cell reaches a terminal state;
Agent trials expose only one canonical tool; ordered evidence records parameters,
errors, retries, tokens, time, and outcomes; safety gates pass; release facts rebuild
deterministically; a second operator reproduces the bundle structure; and real HTTP
and MCP end-to-end paths have been exercised.
