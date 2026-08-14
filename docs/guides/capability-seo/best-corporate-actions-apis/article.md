# Best Corporate Actions APIs for Developers

> Compare four QVeris corporate-actions paths using 72 live split-event calls across nine markets, with latency, public credits, pricing, and evidence limits.

Historical split-event retrieval across US, HK, CN, JP, DE, FR, BR, IN, and ES representative symbols, plus an explicit invalid-symbol control through the tested QVeris Access Paths. This edition compares 4 Providers × 4 Access Paths across nine representative markets using 72 release-backed live calls. Every conclusion is scoped to the tested Access Path and observation window, not the Provider's full native API surface.

This comparison evaluates historical split-event retrieval through the released cohort of Provider and Access Path pairs. It is designed to support choices about representative market coverage, observed gateway behavior, public list-price trade-offs, and invalid-input handling within the frozen evidence boundary; it does not establish universal instrument support or a provider-wide ranking.

## Contents

- [Results at a glance](#results-at-a-glance)
- [How developers should choose](#how-developers-should-choose)
- [Evidence and Provider differences](#evidence-and-provider-differences)
- [What AI Agent builders should verify](#what-ai-agent-builders-should-verify)
- [Method, reproduction, and contribution](#method-reproduction-and-contribution)
- [Limitations, disclosures, and corrections](#limitations-disclosures-and-corrections)
- [FAQ](#faq)

## Results at a glance

| Provider × Access Path | Fixed-sample outcome | Verified representative markets | Median gateway latency | QVeris list credits/call | Official Provider pricing |
|---|---|---|---:|---:|---|
| Alpha Vantage · QVeris connector · [Official site](https://www.alphavantage.co/) · [Try it in QVeris](https://qveris.ai/providers/alphavantage) | Positive 3/3; invalid control 0/3 | US | 485 ms (n=3) | 2 | 25 API requests per day; Premium from USD 49.99/month ([official pricing](https://www.alphavantage.co/premium/); verified 2026-08-10) |
| EODHD · QVeris connector · [Official site](https://eodhd.com/) · [Try it in QVeris](https://qveris.ai/providers/eodhd) | Positive 3/3; invalid control 3/3 | BR, CN, DE, ES, FR, HK, US | 1557 ms (n=3) | 2.81 | 20 API calls per day; All-in-One USD 99.99/month ([official pricing](https://eodhd.com/pricing); verified 2026-08-10) |
| Massive · QVeris connector · [Official site](https://massive.io/) · [Try it in QVeris](https://qveris.ai/providers/massive_stocks) | Positive 3/3; invalid control 0/3 | Evidence insufficient | 1674 ms (n=3) | 1 | Evidence insufficient |
| Twelve Data · QVeris connector · [Official site](https://twelvedata.com/) · [Try it in QVeris](https://qveris.ai/providers/twelvedata) | Positive 3/3; invalid control 0/3 | BR, DE, FR, IN, JP, US | 1086 ms (n=3) | 2.37 | Basic with 8 API credits per minute and 800 per day; Grow from USD 29/month ([official pricing](https://twelvedata.com/pricing); verified 2026-08-10) |

“Verified” means every frozen round met the CAP contract. “Provider-negative” means every round returned an explicit Provider-level negative outcome; it does not prove permanent lack of support. “Not applicable” means the frozen plan excluded that market. “Evidence insufficient” means the Release did not establish either a positive or Provider-negative conclusion.

Read verified as every frozen round for the representative case meeting the capability contract. Provider-negative means every frozen round returned an explicit Provider-level negative outcome, not enduring lack of support. Not-applicable means the Access Path contract excluded the cell rather than the test failing. Evidence-insufficient means the release supports neither a positive conclusion nor a Provider-negative one. Keep these live observations separate from official statements and editorial recommendations.

## How developers should choose

### Broadest released market verification

**Evidence-backed shortlist:** EODHD · QVeris connector. Choose the selected path when verified representative coverage across the released market matrix is the priority. It has the broadest set of verified cells in this release, but inconclusive cells remain unknown and should be checked against the exact target market before adoption.

### A target market where the broadest path is inconclusive

**Evidence-backed shortlist:** Twelve Data · QVeris connector. Choose the selected path when its specific target-market cell is verified while the broader alternative remains evidence-insufficient there. This is a cell-level decision, not permission to infer coverage for every market or instrument.

### Lowest observed gateway latency

**Evidence-backed shortlist:** Alpha Vantage · QVeris connector. Choose the selected path when the released gateway latency sample is the primary runtime constraint. Treat that result as a small observation at the gateway boundary and pair it with the path's narrower applicability before making a production decision.

### Lowest public gateway list price

**Evidence-backed shortlist:** Massive · QVeris connector. Choose the selected path when the frozen public gateway list price is the leading constraint and the representative baseline is sufficient for initial evaluation. Qualify that choice because the market release is evidence-insufficient and direct official pricing evidence is unavailable; list price is not the same as account-billed consumption.

### Explicit invalid-input behavior

**Evidence-backed shortlist:** EODHD · QVeris connector. Choose the selected path when an invalid symbol must produce the released validation outcome instead of empty data or a runtime failure. This observation covers the tested negative control only and does not establish broader recovery, retry, or semantic-error behavior.

These are conditional recommendations from separate evidence dimensions, never an overall score or winner.

## Evidence and Provider differences

### Why Corporate Actions is harder than a basic lookup

A usable split event must preserve instrument identity, event date, and ratio while respecting market-specific symbol dialects. An empty result for a valid historical event and an explicit rejection for an invalid symbol are different outcomes; the CAP keeps them separate so an Agent cannot silently treat transport or entitlement failures as correct Provider behavior.

Corporate-action retrieval is not satisfied by receiving a non-empty payload. The completion contract must bind the requested instrument to the response and extract the action type, effective date, and split ratio; those fields drive downstream position and price-history adjustments, so a plausible record with the wrong identity or semantics is unsafe. Market-qualified symbols make identity handling non-trivial, while the negative control separately tests whether an invalid symbol is surfaced as validation behavior rather than empty or partial data. A successful representative sample proves that contract only for the tested request and path.

### Observed latency and public QVeris list price

[![Latency and QVeris list-price trade-off generated from the Selection Snapshot](charts/latency-list-price-tradeoff.png)](charts/latency-list-price-tradeoff.png)

The horizontal axis is median QVeris gateway latency and the bar shows the observed minimum-to-maximum range. The vertical axis is the sanitized QVeris Inspect list price. These are different dimensions: neither axis represents direct Provider subscription price, personal account billing, or a service-level guarantee.

Read the horizontal and vertical axes together: one represents the frozen public gateway list price and the other the observed gateway latency for the representative baseline. A point can improve one constraint while weakening another, and the latency sample is not a service-level commitment. Use the chart to shortlist paths for a stated constraint, not to derive a composite or provider-wide rank.

### Native plans and QVeris credits are different prices

The comparison table keeps official Provider pricing beside, but separate from, QVeris list credits. Official plan facts carry their own URL and verification date. “Evidence insufficient” is retained when a publishable official price was not frozen for this edition.

### Representative samples across nine markets

[![Corporate Actions test matrix for representative markets and Access Paths](charts/market-coverage.png)](charts/market-coverage.png)

| Provider × Access Path | BR | CN | DE | ES | FR | HK | IN | JP | US |
|---|---|---|---|---|---|---|---|---|---|
| Alpha Vantage · QVeris connector | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 2/2 verified |
| EODHD · QVeris connector | 2/2 verified | 2/2 verified | 2/2 verified | 2/2 verified | 2/2 verified | 2/2 verified | 0/2 Evidence insufficient | 0/2 Evidence insufficient | 2/2 verified |
| Massive · QVeris connector | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0/2 Evidence insufficient |
| Twelve Data · QVeris connector | 2/2 verified | 0/2 Evidence insufficient | 2/2 verified | 0/2 Evidence insufficient | 2/2 verified | 0/2 Evidence insufficient | 2/2 verified | 2/2 verified | 2/2 verified |

Each cell is one representative symbol per market from the market Release. A fraction reports passed rounds over frozen rounds; it is not the percentage of all symbols or exchanges supported.

Read rows as structurally identified Provider and Access Path pairs and columns as representative markets. Each cell reports the released evidence state using the frozen rounds for that representative case; its denominator is those planned rounds, not a count of all instruments in the market. Compare cells only within this observation scope, and do not turn an excluded or inconclusive cell into a failure claim.

### Provider-by-Provider analysis

#### Alpha Vantage · QVeris connector

A released successful sample returned symbol `AAPL`, event date `2020-08-31`, split ratio `4.0`, identity verification `true`. Verified representative markets: US. Observed median gateway latency: 485 ms (n=3). QVeris Inspect list price: 2 credits/call.

This path fits a latency-sensitive evaluation within its explicitly limited market contract. The representative baseline returned the required identity and split-event fields, and the applicable market cell was verified, while other market cells were excluded rather than failed. The invalid-input control did not meet the validation contract, so downstream code should not rely on an explicit validation error from this observation.

#### EODHD · QVeris connector

A released successful sample returned symbol `PETR4.SA`, event date `2008-04-28`, split ratio `2.0`, identity verification `true`. Verified representative markets: BR, CN, DE, ES, FR, HK, US. Observed median gateway latency: 1557 ms (n=3). QVeris Inspect list price: 2.81 credits/call.

This path fits developers prioritizing the broadest released set of verified market cells together with explicit invalid-input behavior. Its representative successful sample met the completion contract, but some applicable market cells remain evidence-insufficient, so the broad result must still be checked at the target-cell level. Its runtime and public list-price position should be weighed separately rather than folded into the coverage result.

#### Massive · QVeris connector

A released successful sample returned symbol `AAPL`, event date `2020-08-31`, split ratio `4.0`, identity verification `true`. Verified representative markets: none in this edition. Observed median gateway latency: 1674 ms (n=3). QVeris Inspect list price: 1 credits/call.

This path fits an initial evaluation driven by the lowest frozen public gateway list price and a completed representative baseline. The separate market release remains evidence-insufficient after observed runtime blocking, so that baseline must not be promoted into a market-coverage claim. The invalid-input control did not meet the validation contract, and official direct-pricing evidence is unavailable in this release.

#### Twelve Data · QVeris connector

A released successful sample returned symbol `PETR4.SA`, event date `2008-04-28`, split ratio `0.5`, identity verification `true`. Verified representative markets: BR, DE, FR, IN, JP, US. Observed median gateway latency: 1086 ms (n=3). QVeris Inspect list price: 2.37 credits/call.

This path fits target-market decisions where its released cell is verified, including cells left inconclusive by another broad-coverage path. Its representative successful sample met the completion contract, but several applicable cells remain evidence-insufficient after runtime errors. The invalid-input control also did not meet the validation contract, so agents need their own normalization and fallback policy.

## What AI Agent builders should verify

| Provider × Access Path | Invalid-input handling | Integration note |
|---|---:|---|
| Alpha Vantage · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |
| EODHD · QVeris connector | 3/3 | Explicit rejection is release-backed. |
| Massive · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |
| Twelve Data · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |

The constrained observation isolates invalid-input handling from other Agent-interface dimensions. Only the path with a positive invalid-input fact produced the required validation outcome; the other observed paths returned empty data or runtime failures for that control. Parameter clarity, schema stability, pagination, and single-tool completion remain evidence-insufficient across the released cohort. Agents should therefore validate returned identity, normalize failure classes, and avoid assuming unmeasured interface fitness.

This is not an AI-friendly score. The current Release does not establish pagination behavior, schema stability across versions, language mapping, single-tool completion. Validate returned identity, market symbol dialect, date semantics, ratio normalization, empty-result behavior in the application boundary.

## Method, reproduction, and contribution

### How we tested

The baseline suite froze a known historical split case and an invalid-symbol control for every included Access Path. The market suite ran applicable representative cases without converting not-applicable or blocked cells into Provider failures. Public terminal evidence is sanitized and digest-bound; private raw responses remain outside the repository.

The baseline Release digest is `sha256:3104ce0ca902bf2aeff7954fc175bd6632adc5b5e56a56011d7a0adf6f89a0ae`. The market Release digest is `sha256:ad621c183b893b54f8aec930ac225066aa9f288c161fdf6a0587e115f1b23463`.

### No key required: reproduce the publication offline

```bash
uv run qveris-bench publication reproduce --package docs/guides/capability-seo/best-corporate-actions-apis/manifest.yaml --expected-package-digest <published-digest>
```

Replace `<published-digest>` with the digest distributed by the trusted GitHub Release or CI attestation outside the checkout. The command rebuilds the Selection Snapshot, writer input, article facts, charts, and guide from committed public evidence without calling QVeris or any Provider; a digest stored only in the same mutable checkout is not a trust anchor.

### With a configured key: start a new live evidence run

```bash
gh workflow run live-corporate-actions-baseline-e2e.yml && gh workflow run live-corporate-actions-market-e2e.yml
```

The workflows read `QVERIS_API_KEY` from the protected `benchmark-e2e` GitHub environment and emit a new artifact set. Release assembly must use a new Release ID; it never overwrites the evidence cited by this edition.

### How Providers and developers can participate

Contributions may add a frozen binding, representative case, publishable pricing fact, sanitized evidence, or factual correction through the repository. Inclusion and conclusions cannot be purchased, and every new claim must remain reproducible from a new immutable Release.

## Limitations, disclosures, and corrections

The evidence covers historical split-event retrieval for representative symbols through the released paths, not every corporate-action type, instrument, exchange, or native Provider surface. Latency comes from a small gateway-boundary sample, public list prices are snapshots rather than billed consumption, and official pricing evidence is separate from live measurements. Representative successes do not establish universal coverage, while Provider-negative and evidence-insufficient outcomes must remain bounded to the frozen observation.

- Representative cases do not prove exhaustive exchange, symbol, instrument, or date-range coverage.
- Latency samples describe the tested QVeris Access Path and observation window, not an SLA.
- QVeris list credits and direct Provider plan prices use different units and scopes.
- This CAP measures historical stock splits, not dividends, mergers, spin-offs, or every corporate-action type.
- Corrections require a new evidence-bound publication package; historical Releases remain immutable.

## FAQ

### Is there a single winner?

No. Select a path by the released dimension that matches the application: target-market evidence, gateway latency, public list price, or invalid-input behavior. Each recommendation carries a different evidence boundary and trade-off.

### Can the publication be reproduced without Provider credentials?

Yes. Use the renderer-provided offline reproduction command to rebuild the publication from the immutable released facts and sanitized public evidence. Offline reproduction verifies the published package; it does not make new Provider calls.

### How is a fresh live edition created?

Use the renderer-provided live rerun workflow with your own credential and create a new immutable Release. A fresh run produces new observations and must not overwrite or silently extend the evidence boundary of this publication.

### How can a Provider contribute evidence or request a correction?

Use the renderer-provided contribution or correction route. New claims should arrive with explicit provenance and enter a new immutable Release; corrections should identify the affected released fact without rewriting the original observation boundary.

### Does a verified representative case prove universal support?

No. Verified applies only when every frozen round for that representative case met the capability contract. It does not establish support for every instrument, market, corporate-action type, or native Provider interface.
