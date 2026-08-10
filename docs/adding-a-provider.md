# Adding a provider

A Provider is an organization; each official API, native MCP endpoint, or QVeris
connector is a distinct Access Path.

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

Never commit credential values, private catalog mappings, managed execution
endpoints, raw responses, personal data, or unlicensed provider material. An excluded
path remains evidence of scope.
