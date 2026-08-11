# Benchmark Governance

This document is the policy source of truth for benchmark independence, official
results, conflicts, challenges, and corrections. Technical contribution steps live
in `CONTRIBUTING.md`.

## Scope and decision rights

Maintainers own suite admission, qualification decisions, official execution,
release approval, and challenge resolution. They must apply the published CAP
contract and evidence rules; they cannot replace an observed result with editorial
preference. A maintainer with a material conflict of interest must recuse from the
decision, and the resolution records the reviewer and disclosed conflict.

Providers and contributors may submit evidence, methods, corrections, and written
responses. They have a right to be heard and to challenge factual errors, but no
right to inclusion, a favorable result, delayed publication, or veto over a result.

## Neutral comparison

- Every compared Provider / Access Path cell uses the same frozen CAP suite,
  outcome rules, and comparable disclosed conditions.
- Provider and Access Path identities remain separate. Native and QVeris results
  use distinct run keys, evidence, environments, and conclusions.
- A Native path that outperforms a QVeris path is published without alteration.
- Infrastructure or benchmark failures are never attributed as Provider failures.
- Missing evidence remains unavailable or evidence-insufficient.
- Aggregate scores, global winners, provider total scores, and Agent-friendly
  ratings are prohibited.

Benchmark decisions cannot be purchased: placement, thresholds, outcomes,
corrections, and withdrawal remain independent. Sponsorship, customer status,
credential access, and other commercial
relationships must be disclosed when they create a conflict of interest and cannot
change benchmark treatment.

## Submission and verification states

These are governance workflow states, not fields that may be written back into an
immutable release. Their coordinates reflect when the state can exist.

- `provider_submitted`: the Provider or its representative supplied an integration,
  self-test, or evidence. The submission binds its Issue, target CAP or frozen suite,
  `provider_id`, and `access_path_id`; no release digest exists yet. It is useful
  review input but cannot publish an official result.
- `maintainer_verified`: an eligible maintainer independently checked the submission
  and performed or supervised the official run under the frozen suite. After
  publication, the record binds the release digest, suite fingerprint,
  `provider_id`, and `access_path_id`.
- `community_reproduced`: an independent contributor performed a new live run and
  disclosed the environment and resulting evidence. It binds the referenced release
  digest, suite fingerprint, `provider_id`, and `access_path_id`. Offline replay
  alone never grants this state.

Future machine-readable verification records must be append-only attestations or
part of a successor release. They cannot mutate historical release bytes.

## Provider admission

A Provider submission must identify the organization, official interface, Access
Path, submitter relationship, authorization and disclosure constraints, and known
conflicts. Credentials are exchanged only through an approved private channel after
maintainer review. A public issue or pull request must never contain credentials,
private raw responses, personal data, or unlicensed material.

Maintainers qualify each Access Path using public policy and publish inclusion or
exclusion with a reason. Inclusion is capability-specific; it does not certify the
Provider globally.

## Challenges and corrections

A result challenge identifies the release ID and release digest, suite fingerprint,
Provider, Access Path, disputed run key or fact, and counter-evidence. Maintainers
record whether the challenge is accepted, rejected, or needs more evidence and
explain the applicable rule.

Published releases are immutable. A factual correction creates a successor release
that cites the previous release and marks it superseded; a material unresolved
integrity problem may mark a release challenged or withdrawn in an append-only
status record. History remains visible. Editorial articles must link to the current
status and never silently rewrite the underlying benchmark fact.

## Changes to benchmark rules

Rule, case, extractor, and outcome changes require review, tests, source provenance,
and a new versioned suite fingerprint. They apply prospectively. Maintainers do not
change a frozen suite to improve or worsen a published Provider result.
