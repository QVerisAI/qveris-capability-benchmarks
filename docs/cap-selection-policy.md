# CAP Selection and Provenance Policy

## Purpose

A `DeveloperScenario` is the versioned representation of what a financial Agent
developer is building. A CAP is one bounded, independently attributable measurement
within that scenario, not a long-horizon workflow or an article topic. Selection
starts from the developer decision, decomposes the scenario into required CAPs, and
ends with versioned, testable definitions whose origins can be audited.

Financial Tasks are the product-facing unit; CAPs are the evaluation unit. Task
composition never merges CAP outcomes into a provider total score.

## Accepted sources

CAP ideas may come from public benchmarks, external task repositories, sanitized
customer questions, developer queries, provider submissions, search demand, or
QVeris-authored research. Source type does not determine inclusion priority.

Before a CAP is executable, its atomic question family belongs in the versioned
`question_bank/`. Every family begins with core-positive and boundary-negative
roles, then adds only the coverage, precision, completeness, and Agent-contract
roles required by its scenarios. The bank records public citations and
QVeris-authored task text; it is an intake asset, not a provider result or a
substitute for a CAP Pack.

How a question is judged is defined in the [question evaluation
model](question-evaluation-model.md): completion conditions and tolerance rules
decide the run cell, Direct Test is mandatory, an Agent Trial receives one
canonical tool, and released dimension facts are `measured`, `declared`, or
`evidence_insufficient` — never an aggregate score.

External repository sources must pin the repository URL, immutable commit, and
source task identifier. Sanitized customer questions use an internal reference that
does not expose the customer, contact details, credentials, or proprietary payloads.

Scenario identity is `(scenario_id, version)`. Its completion policy names which
priority tiers require verified CAP releases and keeps missing dimensions explicitly
`evidence_insufficient`; it never fills a gap from Provider claims or unrelated
scenario questions.

## Definition requirements

Every `cap.yaml` has a stable kebab-case ID, semantic version, plain-language
business use, positive scope, explicit exclusions, and at least one source. Markets
and asset types are recorded when they affect provider applicability.

The catalog is file-backed and deterministic. Duplicate `cap_id + version` entries,
unknown fields, malformed YAML, incomplete provenance, and missing business use fail
validation. Template directories are not catalog entries.

## Versioning

Editorial clarification that does not change cases or applicability may increment a
patch version. Changes to scope, markets, cases, or expected observations require at
least a minor version. An incompatible capability definition requires a major
version. Frozen suites continue to reference their original CAP version.
