# Best Corporate Actions APIs for Developers

> Evidence-backed comparison of QVeris corporate-actions Access Paths for stock splits, with release-backed latency, list credits, market evidence, and Agent signals.

Historical US equity stock-split retrieval and an explicit invalid-symbol control through the tested QVeris Access Paths. This edition covers 4 Providers × 4 Access Paths and 24/24 terminal observations. Every metric below is scoped to the tested Access Path, not the provider's entire native API surface.

## Quick recommendations

- **Lowest observed QVeris list price:** Massive · QVeris connector at 1 credits/call in this frozen inspect snapshot.
- **Lowest observed gateway latency:** Alpha Vantage · QVeris connector at a 480 ms median across 3 samples.
- **Representative-market evidence:** Alpha Vantage, EODHD, Massive, Twelve Data are tied at 1 of 1 tested markets.

These are separate trade-offs, not an overall winner.

## Comparison table

| Provider × Access Path | Fixed-sample outcome | Verified representative markets | Median gateway latency | QVeris list credits/call | Official provider pricing |
|---|---|---|---:|---:|---|
| Alpha Vantage · QVeris connector · [Official site](https://www.alphavantage.co/) · [Try it in QVeris](https://qveris.ai/providers/alphavantage) | Positive 3/3; invalid control 0/3 | US | 480 ms (n=3) | 2 | 25 API requests per day; Premium from USD 49.99/month ([official pricing](https://www.alphavantage.co/premium/); verified 2026-08-10) |
| EODHD · QVeris connector · [Official site](https://eodhd.com/) · [Try it in QVeris](https://qveris.ai/providers/eodhd) | Positive 3/3; invalid control 3/3 | US | 976 ms (n=3) | 2.81 | 20 API calls per day; All-in-One USD 99.99/month ([official pricing](https://eodhd.com/pricing); verified 2026-08-10) |
| Massive · QVeris connector · [Official site](https://massive.io/) · [Try it in QVeris](https://qveris.ai/providers/massive_stocks) | Positive 3/3; invalid control 0/3 | US | 1036 ms (n=3) | 1 | Evidence insufficient |
| Twelve Data · QVeris connector · [Official site](https://twelvedata.com/) · [Try it in QVeris](https://qveris.ai/providers/twelvedata) | Positive 3/3; invalid control 3/3 | US | 1045 ms (n=3) | 2.37 | Basic with 8 API credits per minute and 800 per day; Grow from USD 29/month ([official pricing](https://twelvedata.com/pricing); verified 2026-08-10) |

“Verified” means every frozen round met the CAP contract. “Provider-negative” means every round returned an explicit provider-level negative outcome; it does not prove permanent lack of support. “Not applicable” means the frozen plan explicitly excluded that market.

## Market coverage

| Provider × Access Path | US |
|---|---|
| Alpha Vantage · QVeris connector | 3/3 verified |
| EODHD · QVeris connector | 3/3 verified |
| Massive · QVeris connector | 3/3 verified |
| Twelve Data · QVeris connector | 3/3 verified |

The matrix is one representative symbol per market from the market Release; it is not a claim of full market coverage.

![Market coverage generated from the Selection Snapshot](capability-seo/best-corporate-actions-apis/charts/market-coverage.png)

## Latency and QVeris list-price trade-off

Latency is measured only through the QVeris gateway Access Path. Credits are QVeris inspect list prices, not an individual account's billed consumption or a provider's direct API plan.

![Latency and QVeris list-price trade-off generated from the Selection Snapshot](capability-seo/best-corporate-actions-apis/charts/latency-list-price-tradeoff.png)

## Agent integration notes

| Provider × Access Path | Invalid-input handling | Integration note |
|---|---:|---|
| Alpha Vantage · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |
| EODHD · QVeris connector | 3/3 | Explicit rejection is release-backed. |
| Massive · QVeris connector | 0/3 | No explicit rejection observed; handle failures defensively. |
| Twelve Data · QVeris connector | 3/3 | Explicit rejection is release-backed. |

Do not treat this as an AI-friendly score. Validate the returned instrument identity, event date semantics, currency, pagination, and any market-specific symbol dialect in your own integration.

## How we tested, reproduce, and contribute

The baseline Release digest is `sha256:6e6b8e0235d3beb677f39a973fa5ceda6cca5f2fb5a4ab7269e53b7d2ce342cb`. The market Release digest is `sha256:6ad10146c31b35fb19bbf2aa4cb04188194b4b63cd0fa319932a3f85229cb2b9`. Reproduce the package offline with `qveris-bench publication reproduce --package <package-manifest> --expected-package-digest <published-digest>`. To create a new edition, run the CAP with your own `QVERIS_API_KEY`; a rerun must use a new Release ID and never overwrite this evidence.

Suppliers may submit a binding, reproducible case, or factual correction through the repository. Inclusion and conclusions cannot be purchased.

## Limitations and FAQ

**Does this rank every provider?** No. It compares only the frozen Provider × Access Path cohort for this CAP edition.

**Does a verified market mean all symbols work?** No. It means the representative frozen market case satisfied the contract in every observed round.

**Why can a provider have different results elsewhere?** Native APIs, other connector tools, plan tiers, symbols, and observation dates are different access paths or test conditions.
