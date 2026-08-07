# CAP Selection and Provenance Policy

## Purpose

A Financial Task captures what a financial Agent developer is building. A CAP is
one bounded, independently attributable measurement within that task, not a
long-horizon workflow or an article topic. Selection starts from the developer
decision, decomposes the task into required CAPs, and ends with versioned, testable
definitions whose origins can be audited.

Financial Tasks are the product-facing unit; CAPs are the evaluation unit. Task
composition never merges CAP outcomes into a provider total score.

## Accepted sources

CAP ideas may come from public benchmarks, external task repositories, sanitized
customer questions, developer queries, provider submissions, search demand, or
QVeris-authored research. Source type does not determine inclusion priority.

Before a CAP is executable, its atomic positive and negative tasks belong in the
versioned `question_bank/`. The bank records public citations and QVeris-authored
task text; it is an intake asset, not a provider result or a substitute for a CAP
Pack.

External repository sources must pin the repository URL, immutable commit, and
source task identifier. Sanitized customer questions use an internal reference that
does not expose the customer, contact details, credentials, or proprietary payloads.

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
