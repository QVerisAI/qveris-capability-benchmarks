# CAP Selection and Provenance Policy

## Purpose

A CAP is one bounded, independently attributable measurement, not a long-horizon
workflow or an article topic. Selection starts from a developer decision and ends
with a versioned, testable definition whose origin can be audited.

## Accepted sources

Formal CAPs originate only from a real Harbor catalog contract. Provider
submissions and developer feedback may suggest a candidate, but cannot create a
formal CAP or replace its Harbor provenance.

Before a CAP is executable, its atomic question family belongs in the versioned
`question_bank/`. Every family begins with core-positive and boundary-negative
roles, then adds only the coverage, precision, completeness, and Agent-contract
roles required by its contract. The bank records public citations and
QVeris-authored task text; it is an intake asset, not a provider result or a
substitute for a CAP Pack.

How a question is judged is defined in the [question evaluation
model](question-evaluation-model.md): completion conditions and tolerance rules
decide the run cell, Direct Test is mandatory, an Agent Trial receives one
canonical tool, and released dimension facts are `measured`, `declared`, or
`evidence_insufficient` — never an aggregate score.

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
