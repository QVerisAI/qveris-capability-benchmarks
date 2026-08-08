# Company Research Benchmark v2 Implementation Plan

**Status:** In progress
**Date:** 2026-08-07
**Goal:** Turn the approved provider-selection positioning into one reproducible
Company Research Agent task-fit evidence chain.

## Approach

Keep CAP execution atomic and reuse the existing suite, run, evidence, outcome, and
release pipeline. Add only the file-backed composition contracts that the current
models cannot derive: a developer scenario, question-family roles, and a
release-bound task-fit manifest. Deliver in small PRs; every executable CAP must
finish Direct Test before its facts can appear in the scenario profile.

## Scope

### In

- A versioned `DeveloperScenario` contract for the first Company Research Agent
  composition.
- Question Bank v2 with multiple role-labelled questions per CAP and preserved v1
  question IDs.
- Authority and provenance metadata connecting external benchmark inspiration,
  QVeris-curated question text, and authoritative reference rules.
- Runnable `stock-quote`, `financial-statement-facts`, and
  `sec-filing-evidence` P0 CAP Packs.
- Fixed provider and Access Path qualification, mandatory Direct Test, and eligible
  single-canonical-tool Agent Trial evidence.
- Deterministic, release-bound Task Fit Profile JSON and Markdown that expose
  dimension-level facts, limitations, and evidence status without aggregate scores.

### Out

- Runtime or schema dependencies on `qveris-agent-harness`.
- Stages 5 and 6 services, database, scheduler, leaderboard website, CMS, SEO,
  provider portal, CRM, or external BYOK.
- Provider total scores, Agent-friendly ratings, model rankings, discovery,
  automatic routing, multi-tool planning, or tool-selection metrics.
- Any Provider or Access Path that lacks qualification evidence and authorized
  executable access; missing credentials remain `infra_blocked` or excluded, never
  provider-negative evidence.

## Architecture and impact analysis

The current intake flow is `question_bank/*.yaml` →
`question_bank.repository.load_question_bank()` → CLI validation. It has no consumer
that can compose questions into a developer scenario. The executable flow remains
unchanged: `cap_packs/*` → suite compiler → RunPlan → adapter / Agent backend → raw
and sanitized evidence → categorical outcomes → BenchmarkRelease.

The new scenario layer sits above released CAP facts. It cannot merge CAP runs or
infer missing facts. A Task Fit Profile is a deterministic manifest referencing
immutable releases and evidence digests, not an editorial consumer or live service.

Invariants:

- one question still measures exactly one CAP;
- one run cell still belongs to one CAP, case, Provider, Access Path, mode, and round;
- Direct Test remains mandatory for every included applicable cell;
- an Agent Trial receives exactly one suite-frozen canonical tool;
- native and QVeris paths remain distinct;
- missing dimensions remain `evidence_insufficient`;
- no score, rating, or cross-CAP outcome is introduced;
- credentials and private raw evidence remain outside Git.

## Gap analysis

| Feature | Existing | Gap | Action |
|---|---|---|---|
| Developer-facing composition | Product strategy describes Financial Task → CAP | No validated, versioned composition contract | Create `DeveloperScenario`; existing CAP fields cannot derive user, constraints, required CAPs, or completion policy |
| Question intake | `BankQuestion` has one `cap_id`, observations, conditions, sources | `positive` / `negative` and exact 1+1 validation cannot express coverage, precision, completeness, or Agent contract | Extend the single question-bank path to role-labelled question families; do not keep a legacy parser |
| Question provenance | Public URL, authority tier, citation-only policy | No distinction between scenario inspiration and authoritative truth rule | Extend source metadata and add per-question reference/evaluation contract |
| Existing 20 questions | Stable curated IDs for 10 CAPs | Not linked to a scenario or role taxonomy | Migrate in place and preserve IDs; no duplicate v1 bank |
| Stock Quote | Runnable smoke CAP and released Direct evidence | Insufficient coverage, freshness, precision, and Agent-interface cases for task-fit use | Extend its CAP-owned cases and evidence rules |
| Financial Statement Facts | Candidate question pair | No CAP Pack, provider cohort, extractor, Direct evidence, or release | Create one CAP Pack on the existing Core after qualification |
| SEC Filing Evidence | Candidate question pair | No CAP Pack, provider cohort, extractor, Direct evidence, or release | Create one CAP Pack on the existing Core after qualification |
| Selection dimensions | `ReleaseFact` already rejects aggregate fields and retains evidence refs | Facts lack uniform measured / declared / insufficient state and scenario mapping | Extend `ReleaseFact` details and validation; do not create a parallel score model |
| Agent-interface evidence | One-tool Agent backend and ordered `AgentTrace` exist | CAP question contracts do not require parameter, schema, recovery, or completeness observations | Extend CAP-owned cases/rules and released observations; reuse the backend |
| Task Fit output | Product strategy describes profiles | No deterministic artifact linking scenario dimensions to released facts | Create a file-backed manifest generator that consumes only verified releases |
| Provider cohort | Provider and Access Path qualification pipeline exists | New CAP paths are not yet fixed or terminally qualified | Reuse qualification records; include only authorized/publicly executable paths |
| Release safety | Evidence digests, disclosure, license, and completeness gates exist | New profiles need cross-release reference verification | Extend verification to fail closed on unknown or unsafe release/evidence refs |

Existing release data cannot generate a Developer Scenario because it does not record
the target user, workflow constraints, required CAP set, or scenario completion
policy. Conversely, existing `ReleaseFact` can carry dimension facts, so no new
database, provider aggregate, or duplicate facts table is justified.

## Acceptance criteria

| # | Criterion | Input | Expected | Pass condition |
|---|---|---|---|---|
| AC1 | Validate a versioned Developer Scenario | Company Research scenario YAML | Stable scenario ID/version, user decision, constraints, three P0 CAP refs, and question-family requirements load deterministically | Acceptance test round-trips the model and rejects unknown CAPs/questions |
| AC2 | Support question families without a legacy path | Question Bank v2 YAML | Multiple `core_positive`, `boundary_negative`, `coverage`, `freshness_precision`, `shape_completeness`, and `agent_contract` questions may belong to one CAP | Loader accepts valid families and rejects a CAP missing required core/negative roles |
| AC3 | Preserve v1 intake identity and provenance | Existing 20 question IDs | All IDs survive migration, remain QVeris-authored, and cite valid sources; external text is not copied | Automated set-equality and provenance tests pass |
| AC4 | Express authoritative evaluation contracts | A runnable P0 question | Market/language/as-of semantics, reference source/rule, tolerance where applicable, interface expectations, and selection implication are explicit | Validation fails closed for incomplete runnable contracts |
| AC5 | Keep Core CAP-agnostic | Three P0 CAP Packs | Domain fields and response parsing stay in CAP Packs; shared suite/execution/release code gains no quote/statement/filing vocabulary | Architecture regression test and review pass |
| AC6 | Freeze terminal Provider/Access Path cohorts | Qualification inputs for both new CAPs | Every candidate has included/excluded disposition with evidence; only authorized or public included paths enter suites | Compiler and qualification acceptance tests pass |
| AC7 | Complete mandatory Direct matrices | Included P0 cases × paths × at least three rounds | Every applicable Direct cell reaches `completed` or `provider_negative`; infrastructure failures are not misclassified | Real E2E manifests and release completeness gate pass |
| AC8 | Constrain Agent Trial to one canonical tool | Eligible P0 suite cells | Trial exposes one predetermined tool and records arguments, corrections/errors, calls, tokens, elapsed time, and outcome | Real Agent E2E plus contract test finds no discovery/routing/tool-selection fields |
| AC9 | Publish dimension facts honestly | Verified CAP releases | Accuracy/precision, latency, reliability, cost, coverage, language, Agent-interface, and access constraints are individually `measured`, `declared`, or `evidence_insufficient` with refs | Validation rejects unsupported measured facts and forbidden aggregate fields |
| AC10 | Build a deterministic Task Fit Profile | Scenario + pinned verified CAP releases | JSON and Markdown show provider/path tradeoffs and limitations, preserving separate CAP/path attribution | Two rebuilds are byte-identical and every fact resolves to a release/evidence digest |
| AC11 | Pass security and disclosure gates | All public artifacts | No secret/PII/private raw data; source-license and disclosure status are cleared; sanitized and raw digests stay distinct | Existing and extended release gates plus secret scan pass |
| AC12 | Provide a replayable operator path | Clean checkout with documented inputs | Validation, profile build, release verification, and authorized real E2E commands are reproducible | CLI E2E, changed-area tests, full CI, Ruff, mypy, two reviews, and merged PRs pass |

## Action items

### Task 1 — Question Bank v2 and Developer Scenario

- [ ] Add failing AC1–AC4 tests in `tests/question_bank/`.
- [ ] Extend `src/qveris_bench/question_bank/models.py` and `repository.py` with
  `DeveloperScenario`, role-labelled questions, evaluation contracts, and fail-closed
  cross-reference validation.
- [ ] Migrate `question_bank/*.yaml`, add `question_bank/scenarios.yaml`, update the
  CLI and schemas, and preserve all 20 IDs.
- [ ] Update question-bank, selection-policy, architecture, and repository-map docs.
- [ ] Open the first minimal PR, start CI, run changed-area validation, absorb two
  review lanes once, and merge.

### Task 2 — Stock Quote production question family

- [x] Add coverage, freshness/precision, boundary, and Agent-contract cases for the
  Company Research scenario without invalidating prior release artifacts.
- [x] Freeze versioned cases, truth/tolerance rules, market/language applicability,
  and a credential-safe provider/path cohort.
- [x] Run at least three Direct rounds for every included applicable cell and one
  eligible fixed-tool Agent Trial; build and verify a new immutable release.

The frozen `stock-quote-v3` suite lives in `cap_packs/stock_quote_family/` with a
separate suite-bound binding registry. The verified release
`stock-quote-family-2026-q3-v1` records all 30 Direct cells; the fixed-tool Agent
Trial for the canonical 600519.SH contract runs through its own live workflow.

### Task 3 — Financial Statement Facts CAP

- [x] Build the question family per the [question evaluation model](../question-evaluation-model.md):
  core and boundary roles plus no-data, coverage, shape, and Agent-contract roles
  where the CAP is sensitive; every P0 role must have an executable pass rule.
- [x] Qualify authoritative/public and authorized Provider paths; prefer official
  filings as the truth source and record exclusions terminally.
- [x] Add the CAP Pack, CAP-owned extractors, reference/tolerance rules, cases,
  bindings, suite, and tests on the existing Core.
- [x] Run the fixed Direct matrix and eligible one-tool Agent Trial, then build,
  verify, review, and merge the release PR.

After direct probes, Alpha Vantage income statement and the official SEC company
facts connector returned message-only responses for both CIK forms and were
terminally excluded; the included FSF cohort is FMP as-reported income statement.
The as-reported connector later left QVeris discovery, so the cohort was
re-qualified to the standard FMP income-statement tool; the v2 release
`financial-statements-2026-q3-v2` records all 18 matrix cells completed, including
the CN 600519 coverage case (resolved to the 600519.SS dialect with 10 years of
history). The v3 release `financial-statements-2026-q3-v3` adds QVeris
gateway-side latency and cost observations for every cell.

### Task 4 — SEC Filing Evidence CAP

- [x] Build the question family per the [question evaluation model](../question-evaluation-model.md),
  including citation, document-location, completeness, pagination, and Agent-contract
  roles with executable rules.
- [x] Qualify official filing retrieval and authorized Provider paths with explicit
  citation, document-location, completeness, and error contracts.
- [x] Add the CAP Pack, CAP-owned extraction/rules, cases, bindings, suite, and tests.
- [x] Run the fixed Direct matrix and eligible one-tool Agent Trial, then build,
  verify, review, and merge the release PR.

After direct probes, the FMP 10-K JSON and SEC filings search connectors returned
message-only error responses for both parameter forms and were terminally
excluded; the included SEC evidence cohort is Massive Stocks risk factors.
The v2 release `sec-filing-evidence-2026-q3-v2` records 6 completed and 9
provider_negative cells: the Massive connector intermittently returns an explicit
error envelope (recorded as provider-side filing_unavailable) and the endpoint has
no filing-type parameter (negative control recorded as filing_type_not_supported).
The v3 release `sec-filing-evidence-2026-q3-v3` adds QVeris gateway-side latency
observations for all cells and cost observations for the completed cells.

### Task 5 — Dimension evidence contract

- [x] Extend release validation so each scenario-facing dimension declares
  `measured`, `declared`, or `evidence_insufficient`; measured facts require
  immutable evidence refs that resolve inside the release; environment and plan
  disclosure stays release-level.
- [x] Keep Agent-interface observations separate: parameter contract, response
  schema, error recovery, pagination/completeness, language mapping, and operational
  effort (contract documented in the question evaluation model; enforcement lands
  with the Task 6 profile builder).

### Task 6 — Task Fit Profile

- [x] Add a deterministic builder and verifier that consume only pinned, verified
  CAP releases and emit versioned JSON plus Markdown.
- [x] Show per-CAP Provider/Access Path tradeoffs, evidence states, and limitations;
  fail closed on missing refs and forbid all aggregate score/rating fields.

The Company Research Task Fit Profile v1 lives in `profiles/` and references the
three verified P0 releases (`stock-quote-family-2026-q3-v1`,
`financial-statements-2026-q3-v1`, `sec-filing-evidence-2026-q3-v1`).

### Task 7 — Replay and release acceptance

- [x] Document the clean-checkout operator flow and exact environment-variable names
  without values.
- [x] Rebuild artifacts twice, verify digests, run all changed-area tests, CLI E2E,
  Ruff, mypy, and CI, and preserve private/public evidence separation.

### Task 8 — PR and review completion

- [x] Keep each PR reviewable and PR-first; resolve conflicts before broad testing.
- [x] After each PR, run the required two review lanes, classify all findings, fix
  actionable P0/P1 and valid P2 items in one pass, revalidate once, and merge.
- [x] Mark the goal complete only after all three P0 CAP releases and the verified
  Company Research Task Fit Profile are merged.

## Validation plan

- Question/scenario schema tests map directly to AC1–AC4.
- CAP Pack/compiler/extractor tests map to AC5–AC6.
- Real Direct HTTP/MCP execution and fixed-tool Agent E2E map to AC7–AC8.
- Release/profile contract, canonical rebuild, and negative validation tests map to
  AC9–AC11.
- Installed CLI execution, clean-checkout replay, Ruff, mypy, CI, and two review
  lanes map to AC12.

Mock transport tests may test failure handling but cannot satisfy AC7 or AC8. A
credential or entitlement failure is recorded as infrastructure evidence and does
not become a Provider capability conclusion.

## Delivery sequence

```text
Question Bank v2 + Scenario
  -> Stock Quote production family
  -> Financial Statement Facts release
  -> SEC Filing Evidence release
  -> Dimension fact contract
  -> Company Research Task Fit Profile
  -> replay acceptance and final merge
```

The sequence may use separate PRs, but it keeps one production path and one active
goal. Later tasks may start while a prior PR runs CI only when their files do not
overlap; every task still closes its own AC, review, and merge loop.
