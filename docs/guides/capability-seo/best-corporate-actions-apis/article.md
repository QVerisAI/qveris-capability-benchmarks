# Best Corporate Actions APIs for Developers

> Evidence-backed comparison of QVeris corporate-actions Access Paths for stock splits, with release-backed latency, list credits, market evidence, and Agent signals.

Historical US equity stock-split retrieval and an explicit invalid-symbol control through the tested QVeris Access Paths. This edition covers 4 Providers × 4 Access Paths and 24/24 terminal observations. Every metric below is scoped to the tested Access Path, not the provider's entire native API surface.

## Quick recommendations

- **Lowest observed QVeris list price:** Massive · QVeris connector at 1 credits/call in this frozen inspect snapshot.
- **Lowest observed gateway latency:** Alpha Vantage · QVeris connector at a 480 ms median across 3 samples.
- **Broadest representative-market evidence:** Alpha Vantage · QVeris connector verified 1 of 1 tested markets.

These are separate trade-offs, not an overall winner.

## Comparison table

| Provider × Access Path | Fixed-sample outcome | Verified representative markets | Median gateway latency | QVeris list credits/call |
|---|---|---|---:|---:|
| Alpha Vantage · QVeris connector · [Official site](https://www.alphavantage.co/) · [Try it in QVeris](https://qveris.ai/providers/alphavantage) | Positive 3/3; invalid control 0/3 | US | 480 ms (n=3) | 2 |
| EODHD · QVeris connector · [Official site](https://eodhd.com/) · [Try it in QVeris](https://qveris.ai/providers/eodhd) | Positive 3/3; invalid control 3/3 | US | 976 ms (n=3) | 2.81 |
| Massive · QVeris connector · [Official site](https://massive.io/) · [Try it in QVeris](https://qveris.ai/providers/massive_stocks) | Positive 3/3; invalid control 0/3 | US | 1036 ms (n=3) | 1 |
| Twelve Data · QVeris connector · [Official site](https://twelvedata.com/) · [Try it in QVeris](https://qveris.ai/providers/twelvedata) | Positive 3/3; invalid control 3/3 | US | 1045 ms (n=3) | 2.37 |

“Verified” means every frozen round met the CAP contract. “Provider-negative” means every round returned an explicit provider-level negative outcome; it does not prove permanent lack of support. “Not applicable” means the frozen plan explicitly excluded that market.

## Market coverage

| Provider × Access Path | US |
|---|---|
| Alpha Vantage · QVeris connector | 3/3 |
| EODHD · QVeris connector | 3/3 |
| Massive · QVeris connector | 3/3 |
| Twelve Data · QVeris connector | 3/3 |

The matrix is one representative symbol per market from the market Release; it is not a claim of full market coverage.

![Market coverage generated from the Selection Snapshot](charts/market-coverage.png)

## Latency and QVeris list-price trade-off

Latency is measured only through the QVeris gateway Access Path. Credits are QVeris inspect list prices, not an individual account's billed consumption or a provider's direct API plan.

![Latency and QVeris list-price trade-off generated from the Selection Snapshot](charts/latency-list-price-tradeoff.png)

## Agent integration notes

| Provider × Access Path | Invalid-input handling | Integration note |
|---|---:|---|
| Alpha Vantage · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |
| EODHD · QVeris connector | 3/3 | Explicit rejection is release-backed. |
| Massive · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |
| Twelve Data · QVeris connector | 3/3 | Explicit rejection is release-backed. |

Do not treat this as an AI-friendly score. Validate the returned instrument identity, event date semantics, currency, pagination, and any market-specific symbol dialect in your own integration.

## How we tested, reproduce, and contribute

The baseline Release digest is `sha256:46d41a05b136affcf2b1424f6c331fac9aacf65d33c8ef9233f032e5506264aa`. The market Release digest is `sha256:a67160d4a075c6a0def5bf76426999a176a2d14a8557b51dbdaeb72b3dd68587`. Reproduce the package offline with `qveris-bench publication reproduce --package <package-manifest> --expected-package-digest <published-digest>`. To create a new edition, run the CAP with your own `QVERIS_API_KEY`; a rerun must use a new Release ID and never overwrite this evidence.

Suppliers may submit a binding, reproducible case, or factual correction through the repository. Inclusion and conclusions cannot be purchased.

## Limitations and FAQ

**Does this rank every provider?** No. It compares only the frozen Provider × Access Path cohort for this CAP edition.

**Does a verified market mean all symbols work?** No. It means the representative frozen market case satisfied the contract in every observed round.

**Why can a provider have different results elsewhere?** Native APIs, other connector tools, plan tiers, symbols, and observation dates are different access paths or test conditions.
