# Government Bond Yield CAP Article Design

## Outcome

Produce a new evidence-backed English comparison article for developers selecting a QVeris Access Path for dated 10-year sovereign benchmark yields. This is a cold-start stability test of the reusable CAP Article Factory, not a one-off hand-written guide.

The publication is complete only when a reader can inspect the seven-country evidence, compare latency and public QVeris list credits, understand yield-unit and benchmark-identity risks, and reproduce the package offline without Provider credentials.

## Selected CAP and scope

- Harbor capability: `RATES.GOVT_BENCHMARK`
- Contract version: `1`
- CAP identity: `govt-bond-yield`
- Positive markets: US, CN, UK, DE, JP, AU, CA
- Frozen tenor: 10Y
- Negative control: unsupported country `ZZ` with tenor 10Y
- Rounds: two per applicable Provider × Access Path × case
- Maximum Provider executions: 36 for the two-path publishable cohort after the Alpha Vantage candidate fails the country-negative gate

The CAP measures dated sovereign benchmark yield observations. It does not measure full yield curves, central-bank policy rates, corporate bonds, real-time tradable prices, or every maturity.

## Alternatives considered

1. Real-time Financial News offered the largest Provider cohort but required a domain-specific freshness and relevance publication profile before the market-coverage pipeline could be tested.
2. Financial Ratios and Valuation had only two Harbor Providers and risked producing another structurally complete but low-information comparison.
3. Government Bond Yields was selected because its three-Provider cohort and seven-country contract exercise the same reusable market evidence path while adding unit, source, date, and benchmark-identity semantics.

## One production path

```text
Harbor contract snapshot
  → candidate discovery and terminal dispositions
  → formal CAP Pack and frozen Direct Binding Registry
  → baseline Suite (US + ZZ) and market Suite (all seven countries)
  → GitHub-hosted QVeris Direct Tests using benchmark-e2e secret
  → sanitized public terminals + private raw envelopes
  → immutable baseline and market Releases
  → Selection Snapshot
  → writer-input.json
  → CAP Article Writer editorial.json
  → deterministic article, charts, manifest, and external attestation
  → offline publication reproduce
```

No parallel runner, hand-authored fact table, or legacy CAP path is introduced. Core stays generic; bond-yield extraction and outcome rules live in the versioned CAP Pack.

## CAP completion contract

A positive cell completes only when the terminal evidence establishes:

- the returned benchmark belongs to the requested country and 10Y tenor;
- at least one observation has an ISO date and finite numeric closing yield;
- the observation date is inside the frozen request window;
- the unit is observed or explicitly marked evidence-insufficient, never inferred;
- source and currency remain optional observations and are not fabricated;
- empty, malformed, cross-country, or wrong-tenor payloads do not pass.

Every positive binding uses the fixed window `2024-01-01` through `2024-12-31` and deterministically selects the latest valid observation in that window. Zero and negative sovereign yields remain valid finite numeric observations. Provider-returned identity must match a frozen alias when present; otherwise the fact is explicitly request-bound. Optional unit, currency, and source fields are preserved when present and remain evidence-insufficient when absent.

The `ZZ` negative control completes only on an explicit Provider-level rejection or empty unsupported result allowed by the CAP rule. Authentication, entitlement, rate limiting, server errors, parse failures, and timeouts remain infrastructure-blocked outcomes.

## Provider and Access Path discovery

The public Harbor snapshot reports a provider count of three but does not publish the Provider identities. Discovery therefore runs through the existing `qveris-discovery.yml` workflow with the protected `QVERIS_API_KEY`; the resulting cohort is described as the frozen QVeris Provider × Access Path cohort, not as an asserted Harbor Provider list.

Every discovered Tool receives a terminal disposition. A Provider enters the direct-test cohort only when one frozen QVeris Access Path exposes a safe request shape for the CAP. Qualification selects at most one canonical Tool per frozen Provider identity through a versioned deterministic rule; alternate and alias candidates retain explicit dispositions. Provider and Access Path IDs remain separate in binding IDs, run keys, evidence, Releases, Snapshot rows, tables, and prose.

If fewer than two applicable Provider × Access Path rows survive discovery and preflight, publication stops as evidence-insufficient instead of manufacturing a ranking.

## Evidence and release design

Two Releases keep baseline behavior and country coverage independently auditable:

- Baseline Release: US 10Y plus the `ZZ` negative control, exactly 8 planned Execute calls.
- Market Release: all seven US, CN, UK, DE, JP, AU, and CA 10Y cases, exactly 28 planned Execute calls.

Each public terminal is derived from one private execution envelope that binds run key, Provider, Access Path, Tool, canonical parameter digest, response digest, transport status, latency, and sanitized facts. Public evidence omits credentials, raw response bodies, signed URLs, and account-billed credits.

Release replay must validate Harbor provenance, frozen bindings, exact evidence file sets, public-manifest bytes, GitHub artifact attestation, terminal outcomes, and canonical Release digest without network access.

## Selection Snapshot

One row per Provider × Access Path projects only released facts:

- positive and negative completion rounds;
- country states: verified, provider-negative, not-applicable, or evidence-insufficient;
- latency median/min/max and sample count;
- sanitized QVeris Inspect list credits;
- official Provider pricing only when a scoped official fact is frozen;
- separate Snapshot Agent-interface observations for invalid input, plus digest-bound public terminal facts in writer input for benchmark identity, date, unit, currency, and source.

Account-billed `cost_credits` is forbidden from public terminals, Releases, Snapshot facts, and the article.

## Article and charts

Primary intent: developers comparing government bond yield APIs for multi-country 10Y benchmark data.

The deterministic renderer owns all names, values, dates, fractions, links, digests, commands, tables, and chart paths. The CAP Article Writer produces only evidence-referenced editorial prose.

Reader flow:

1. answer-first scope and evidence boundary;
2. conditional recommendations without an overall winner;
3. Provider × Access Path comparison table;
4. seven-country evidence matrix;
5. latency × public QVeris list-credit trade-off;
6. yield unit, currency, source, date, and benchmark identity notes;
7. Provider-by-Provider analysis;
8. method, offline reproduction, live rerun, contribution, limits, corrections, and FAQ.

The country chart shows Provider names without repeating a common `QVeris connector` suffix. If a Provider has multiple Access Paths, the chart retains enough path identity to distinguish the rows.

## Failure handling

- Discovery mismatch: stop and preserve dispositions; do not guess Provider IDs.
- Missing or unsafe binding: mark the candidate non-runnable; do not execute it.
- Transport or entitlement failure: preserve infra attribution; do not convert it to Provider-negative.
- Incomplete matrix: do not assemble a formal Release or article.
- Snapshot or downstream drift: publication reproduction fails until every dependent artifact is rebuilt.
- Canonical Linux chart mismatch: CI fails publication; non-Linux may ignore encoding bytes only when complete RGBA pixels match.
- Existing Release ID: assembly fails; every rerun uses a successor ID.

## Verification

- CAP acceptance tests cover contract provenance, binding identity, date window, finite yields, country/tenor identity, negative control, and transport attribution.
- Live E2E covers every frozen matrix cell through the real QVeris gateway.
- Release assembly tests validate GitHub/private artifact provenance and exact matrix closure.
- Selection tests reject Release, price, Provider, Access Path, or country-state drift.
- Article tests compare the rendered structure with the Dividend Golden CAP rubric and reject invented or contradictory material claims.
- Publication E2E replays both Releases, rebuilds Snapshot and writer input, regenerates charts/article, checks the published guide, and verifies an external package digest.
- Changed-area tests, Ruff, mypy, full Linux CI, and two parallel PR reviewers must pass before merge.

## Stability measurement

Record elapsed time and manual interventions for discovery, CAP freeze, live execution, Release assembly, Snapshot generation, editorial generation, and publication validation. The pipeline is considered stable when failures are fail-closed and a future unchanged-shape CAP can reuse the same commands and artifact contracts without a CAP-specific parallel article renderer.
