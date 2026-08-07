# Adding a provider

A Provider is an organization; each official API, native MCP endpoint, or QVeris
connector is a distinct Access Path.

1. Create `providers/<provider>/provider.yaml` from the template.
2. Record official source, canonical interface, credential environment-variable
   names only, and testing authorization for every Access Path.
3. Assign every candidate a terminal qualification, inclusion or exclusion, with
   reason and evidence digest. Qualification is not a score.
4. Run `qveris-bench provider validate` and `qveris-bench provider cohort-check`.
5. Bind included paths to a CAP suite without merging Native and QVeris evidence.

Never commit credential values, raw responses, personal data, or unlicensed
provider material. An excluded path remains evidence of scope.
