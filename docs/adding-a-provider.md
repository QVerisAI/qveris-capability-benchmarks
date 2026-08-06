# Adding a provider

A Provider represents an organization; each official API, native MCP endpoint,
or QVeris connector is a separate Access Path.

1. Create `providers/PROVIDER/provider.yaml` from the template.
2. Record official source, canonical interface, credential environment-variable
   names only, and testing authorization for every Access Path.
3. Assign one terminal qualification to every candidate: included or excluded,
   with reason and evidence digest. This is terminal qualification, not a score.
4. Run `qveris-bench provider validate` and `qveris-bench provider cohort-check`.
5. Bind only included paths to a CAP suite. Native and QVeris paths must retain
   distinct identities and evidence.

Never commit credential values, raw responses, personal data, or unlicensed
provider materials. An excluded path remains evidence of scope; do not silently
remove it to improve a result.
