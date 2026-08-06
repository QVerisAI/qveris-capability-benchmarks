# Provider and Access Path Qualification Policy

## Identity boundary

A Provider identifies the organization or product. An Access Path identifies one
official or explicitly labeled machine interface. Native API, native MCP, official
OpenAPI, SDK, benchmark wrapper, and QVeris connector paths remain separate records,
run keys, evidence, and release rows even when they reach the same underlying data.

## Candidate requirements

Every candidate records its official name, website, market coverage, test
authorization, QVeris integration status, and one or more Access Paths. Each Access
Path records official provenance, plan, authorization, canonical interface, Agent
Trial eligibility, and environment-variable names for required credentials.

Credential values never enter YAML, traces, CLI output, or cohort decisions. A
credential check may report only which configured environment-variable names are
missing.

## Terminal qualification

A frozen cohort accepts only `included` and `excluded` terminal dispositions for
each Access Path. Every decision requires a plain-language reason and a SHA-256
evidence reference. One Provider may therefore have an included native interface
and an excluded QVeris or wrapper path without conflating their evidence.
Unavailable credentials, unclear authorization, unsupported markets, and duplicate
or unofficial interfaces are explicit exclusion reasons rather than silent drops.

Qualification establishes whether an Access Path may enter a Suite. It does not
rank the Provider or predict benchmark results. Provider-negative benchmark evidence
is produced only by execution after suite freeze.
