# Adding a Provider

A Provider is an organization. Each official API, native MCP endpoint, or QVeris
connector is a distinct Access Path with independent run keys, evidence, and results.
The governing admission and verification rules are in
[GOVERNANCE.md](../GOVERNANCE.md).

## Start a submission

Open the Provider submission form linked from `CONTRIBUTING.md`. Identify the
Provider, official interface, Access Path type, your relationship to the Provider,
authorization and disclosure constraints, and conflicts of interest.

Do not put an API key, private raw response, managed endpoint, personal data, or
unlicensed material in an Issue or pull request. After the public scope is accepted,
maintainers arrange an approved private credential channel when a live test requires
Provider-supplied access.

A Provider self-test is `provider_submitted` evidence. It cannot become an official
result until an eligible maintainer rerun qualifies and executes the Access Path.
Independent contributors may later add `community_reproduced` evidence without
modifying the original release.

## Registry contribution

1. Create `providers/<provider>/provider.yaml` from the template.
2. Add `official_pricing` facts with the official URL, applicable product or Access
   Path scope, original currency, verification date, content digest, and public
   disclosure/license provenance.
3. Record protocol, a public official endpoint when available, authentication method,
   and separate benchmark authorization for every Access Path. Managed execution
   endpoints and credential references do not belong in the public Provider registry.
4. Assign every candidate a terminal qualification, inclusion or exclusion, with
   reason and evidence digest. Qualification is not a score.
5. Run `qveris-bench provider validate providers/<provider>/provider.yaml` and
   `qveris-bench provider cohort-check --root providers`.
6. Bind included paths to a CAP suite without merging Native and QVeris evidence.

Admission is CAP-specific and does not certify the Provider globally. Maintainers may
exclude an Access Path when authorization, licensing, stability, or evidence is
insufficient; the reason remains public and can be challenged with new evidence.
