# Best Dividend APIs for Developers in 2026: 6 Providers

There is no single best dividend API for every application. Through the tested QVeris Access Paths, Twelve Data, Alpha Vantage, EODHD, and Massive returned the required ex-dividend date and single-event amount for the fixed AAPL sample. Their published facts do not independently prove that each response identified `AAPL`, so production identity validation remains necessary. Hang Seng's tested QVeris Access Path passed the representative mainland China sample with a response security code that matched the request.

This dividend API comparison treats a successful response as only the starting point. A dividend data API must let your application verify the **security identity, ex-dividend date, and cash amount per share for one event**. Among the US samples, Alpha Vantage and Massive exposed the broadest event-date sets, while Twelve Data and Massive explicitly returned currency. The iFinD Native MCP returned an annual cumulative per-unit dividend, but not a dated, single Dividend Event.

We made 102 live calls across two test suites, including invalid-symbol controls and representative symbols from US, HK, CN, JP, DE, FR, BR, IN, and ES. These **representative market sample results** are not claims about every security, date range, entitlement, or market a provider covers.

> **Quick recommendation:** Through the tested QVeris Access Paths, start by reproducing Twelve Data, Alpha Vantage, EODHD, or Massive for basic US Dividend Events. For broader representative-market results, EODHD passed 7 markets and Twelve Data passed 6. Alpha Vantage passed all 4 markets that QVeris marked applicable; we did not spend calls retesting the other 5 explicitly unsupported markets.

## Contents

- [Results at a glance](#results-at-a-glance)
- [How developers should choose](#how-developers-should-choose)
- [Evidence and provider differences](#evidence-and-provider-differences)
- [What AI Agent builders should verify](#what-ai-agent-builders-should-verify)
- [Method, reproduction, and contribution](#method-reproduction-and-contribution)
- [Limitations, disclosures, and corrections](#limitations-disclosures-and-corrections)
- [FAQ](#faq)

## Results at a glance

The baseline test ran on August 11, 2026. Each applicable Access Path had one positive security sample and one invalid-symbol negative control, each repeated three times: 36 live calls. The market test ran on August 12, 2026. It included 27 applicable positive cells plus one negative control for each of the six paths, repeated twice: 66 live calls. The two Releases remain separate and are not combined into a score.

| Provider and Access Path | Dividend Event sample result | Median QVeris gateway latency / public QVeris Inspect price | Native official pricing | 9 representative market samples |
|---|---|---:|---|---|
| [Hang Seng](https://www.gildata.com/products/core-data.html) (QVeris) · [Try it in QVeris](https://qveris.ai/providers/hangseng_polysource) | **CN sample passed:** both rounds returned a verifiable security identity, ex-dividend date, and single-event amount | 623 ms / 1 credit/call | No public standard price; contact sales | CN passed (2/2); other 8 not tested: explicitly not applicable |
| [iFinD](https://mcp.51ifind.com/gwstatic/static/ds_web/ifind-mcp-web/skills/SKILL_INSTALL_GUIDE.md) (Native MCP) | **Sample did not pass:** no single-event date, and the annual cumulative value cannot establish the amount for one event | Not applicable; Native MCP is excluded from QVeris metrics | Personal CNY 40/month for 5,000 requests | US, HK, and CN samples did not pass (0/2); other 6 not tested: explicitly not applicable |
| [Twelve Data](https://twelvedata.com/docs#dividends) (QVeris) · [Try it in QVeris](https://qveris.ai/providers/twelvedata) | **Sample passed:** AAPL returned an ex-dividend date and single-event amount in all three rounds; the invalid symbol produced no fabricated event | 491 ms / 2.37 credits/call | Grow from USD 29/month; free tier 800 credits/day | 6 markets passed (2/2); HK, CN, and ES samples did not pass (0/2) |
| [Alpha Vantage](https://www.alphavantage.co/documentation/#dividends) (QVeris) · [Try it in QVeris](https://qveris.ai/providers/alphavantage) | **Sample passed:** both the AAPL sample and invalid-symbol control met the contract in all three rounds | 576 ms / 0 credits/call | Premium from USD 49.99/month; free tier 25 requests/day | 4 applicable markets passed (2/2); 5 not tested: explicitly not applicable |
| [EODHD](https://eodhd.com/financial-apis/api-splits-dividends/) (QVeris) · [Try it in QVeris](https://qveris.ai/providers/eodhd) | **Sample passed:** both the AAPL sample and invalid-symbol control met the contract in all three rounds | 779 ms / 2.81 credits/call | All-in-One USD 99.99/month | 7 markets passed (2/2); JP and IN samples did not pass (0/2) |
| [Massive](https://massive.com/docs/rest/stocks/corporate-actions/dividends) (QVeris) · [Try it in QVeris](https://qveris.ai/providers/massive_stocks) | **Sample passed:** both the AAPL sample and invalid-symbol control met the contract in all three rounds | 861 ms / 1 credit/call | [Stocks Basic Free](https://massive.com/pricing?product=stocks); Dividend endpoint included in all Stocks plans | US passed (2/2); other 8 not tested: explicitly not applicable |

These four public states describe evidence, not a final procurement decision:

- **Sample passed:** every frozen round completed the task defined by this benchmark.
- **Sample did not pass:** live calls completed, but the result lacked required fields or business meaning.
- **Evidence insufficient:** the published evidence cannot support either conclusion; this does not mean the provider lacks the capability.
- **Not tested: explicitly not applicable:** QVeris or the Access Path contract explicitly excludes the market, so we did not spend calls probing it again.

“Sample passed” is not a production SLA and does not establish support for every security, market, date range, or licensing scenario.

## How developers should choose

### You only need a US ex-dividend date and single-event amount

The tested QVeris Access Paths for Twelve Data, Alpha Vantage, EODHD, and Massive should be on the first reproduction shortlist. Then compare three engineering dimensions: the fields your product needs, the QVeris list price per call, and P95/P99 latency measured again from your deployment region.

### You need declaration, record, and payment dates

For US workflows, reproduce the tested QVeris Access Paths for Alpha Vantage and Massive first because those fields appeared in the published samples. For mainland China, Hang Seng's tested sample exposed the same additional date types. A field appearing once does not mean every historical record is complete, so production acceptance should also measure missing-field rates and historical depth.

### Currency must be explicit in the response

Start with Twelve Data and Massive. Both explicitly returned `currency` in this sample. When another path omits it, leave it null or enrich it from a separately sourced dataset—do not silently infer it from the exchange.

### Your primary use case is mainland China dividends

Hang Seng's representative CN sample passed both rounds and is the first candidate to reproduce. The iFinD Native MCP still lacked a single-event date and amount meaning in both CN rounds.

### You want one key for several data sources

A QVeris Access Path reduces authentication and protocol differences. One key does not standardize provider semantics, so security identity, dates, and amounts still need the same CAP checks across every path.

## Evidence and provider differences

### Why a Dividend Event is harder than “get dividends”

A machine-usable event must answer four questions: which security, what ex-dividend date, what cash amount per share for this event, and whether an empty response means “no event” or “request failed.” Declaration, record, and payment dates are valuable extensions, but they cannot replace the ex-dividend date. Currency must not be inferred from the market when it is absent.

The same security may appear as `AAPL`, `600519.SH`, or a provider-specific identifier. Even plausible dates and amounts are unsafe if the returned security cannot be tied back to the requested one.

### Core usability versus field richness

Core fields determine whether a record can enter a business system: security identity, ex-dividend date, and single-event amount are all required. Currency, declaration date, record date, and payment date enrich an event model, but a field appearing in a sample does not guarantee it is present on every record. Validate core usability first, then compare optional fields required by your application.

### Observed latency and public QVeris list price

[![Latency and QVeris Inspect list-price trade-off for five dividend Access Paths](capability-seo/best-dividend-apis/charts/dividend-runtime-tradeoff.png)](capability-seo/best-dividend-apis/charts/dividend-runtime-tradeoff.png)

The x-axis is median QVeris gateway latency; each horizontal bar spans the observed minimum to maximum across six calls. The y-axis is the public list price returned by `qveris inspect`, not the actual charge to the test account. Because that account receives a discount, this article does not use account billing in its tables or charts.

Twelve Data had the lowest median latency in this sample. Alpha Vantage had the lowest Inspect price at 0 credits/call, followed by Hang Seng and Massive at 1 credit/call. EODHD had both the highest list price and highest observed median latency. Six calls can prioritize a reproduction test; they cannot predict regional performance, P95/P99, or a provider's Native API SLA.

### Native plans and QVeris credits are different prices

| Provider / Access Path | Free or trial entry | Paid entry | Scope of price evidence |
|---|---|---|---|
| [Hang Seng / QVeris](https://www.gildata.com/products/core-data.html) | `Not published for this snapshot.` | `Commercial; see product page.` | Provider product page; QVeris list price comes from the Inspect snapshot |
| [iFinD / Native MCP](https://mcp.51ifind.com/?syncCookieTimes=1#/pricing) | `New accounts receive 2,000 trial requests` | `Personal CNY 40/month for 5,000 requests; Enterprise CNY 5,000/month for 1,000,000 requests` | Native MCP only |
| [Twelve Data / QVeris](https://twelvedata.com/pricing) | `Basic with 8 API credits per minute and 800 per day` | `Grow from USD 29/month` | Provider-wide official price; QVeris price verified per Tool |
| [Alpha Vantage / QVeris](https://www.alphavantage.co/premium/) | `25 API requests per day` | `Premium from USD 49.99/month` | Provider-wide official price; QVeris price verified per Tool |
| [EODHD / QVeris](https://eodhd.com/pricing) | `20 API calls per day` | `All-in-One USD 99.99/month` | Provider-wide official price; QVeris price verified per Tool |
| [Massive / QVeris](https://massive.com/pricing?product=stocks) | `Stocks Basic Free` | `Stocks Starter USD 29/month` | Official documentation includes Dividends in all Stocks plans; QVeris price verified per Tool |

Provider subscriptions, QVeris credits, and actual test-account charges are three different facts. Plans may also differ by real-time access, exchange fees, caching, and redistribution rights, so monthly price alone is not enough for procurement.

### Representative samples across nine markets

[![Dividend Event test matrix for nine representative markets and six Access Paths](capability-seo/best-dividend-apis/charts/dividend-market-coverage.png)](capability-seo/best-dividend-apis/charts/dividend-market-coverage.png)

Green means the fixed representative symbol returned a verifiable security identity, ex-dividend date, and single-event cash amount in both rounds. Orange means both calls ran but did not produce a valid Dividend Event. Gray means QVeris or the Access Path contract explicitly marked the market not applicable, so we did not probe it again.

| Provider / Access Path | Representative markets passed (2/2) | Representative sample did not pass (0/2) | Not tested: explicitly not applicable |
|---|---|---|---|
| Hang Seng / QVeris | CN | — | US, HK, JP, DE, FR, BR, IN, ES: contract limited to mainland China exchanges |
| iFinD / Native MCP | — | US, HK, CN: no single-event date or amount meaning | JP, DE, FR, BR, IN, ES: contract declares only US/HK/CN |
| Twelve Data / QVeris | US, JP, DE, FR, BR, IN | HK, CN, ES | — |
| Alpha Vantage / QVeris | US, CN, FR, ES | — | HK, JP, DE, BR, IN: explicitly unsupported by QVeris |
| EODHD / QVeris | US, HK, CN, DE, FR, BR, ES | JP, IN | — |
| Massive / QVeris | US | — | HK, CN, JP, DE, FR, BR, IN, ES: Stocks Access Path applies to US equities |

`2/2` is repeatability evidence, not statistical certification of an entire market. `0/2` means only that the selected symbol and window failed the task in both rounds; it does not prove that the provider does not support the market. Before production, rerun the same checks with your symbols, permissions, date ranges, and licensing requirements.

The market Release contains 120 planned test cells. All 66 applicable cells have sanitized public evidence, while the other 54 retain an explicit not-applicable reason. Unknown states, temporary failures, and missing evidence cannot be relabeled as not applicable.

### Provider-by-provider analysis

#### Hang Seng: representative CN sample passed

The representative CN sample returned a verifiable security identity, ex-dividend date, and single-event amount in both rounds. It is a priority candidate for reproducing mainland China dividend events with your own symbols, date range, and permissions.

#### iFinD: an annual cumulative value is not a single event

The iFinD Native MCP returned an annual cumulative per-unit dividend in all three baseline rounds but no verifiable ex-dividend date. That value cannot establish the amount of one event, so it does not satisfy this article's event-calendar, ex-date backtest, or price-adjustment use cases. We tested only the official Native MCP and do not provide a QVeris CTA for iFinD.

#### Twelve Data: direct core fields with explicit currency

The AAPL sample returned `effective_date`, `amount`, and `currency`, making it a reproduction candidate for basic US dividend calendars and notifications. We did not measure pagination limits, complete market scope, or plan quotas.

#### Alpha Vantage: richer event dates in the sample

In addition to the required fields, the sample included declaration, record, and payment dates. This makes Alpha Vantage a priority reproduction candidate for multi-stage event models, but it does not prove those fields are complete across all records.

#### EODHD: core fields in a compact shape

The public facts include ex-dividend date, amount, and event count. We did not infer currency or additional dates. EODHD is a candidate for normalized core events; applications that require declaration date, payment date, or currency should add those fields to their own acceptance tests.

#### Massive: rich fields with a clear Stocks plan entry point

The sample included currency, declaration date, record date, ex-dividend date, and payment date. Massive's official documentation lists the Dividends endpoint in all Stocks plans, so individual developers can begin with Stocks Basic Free. Through QVeris, the corresponding Tool's Inspect price was 1 credit/call.

## What AI Agent builders should verify

We did not run an Agent Trial and do not publish an aggregate Agent rating. For an Agent, field count is not enough: identity provenance, error meaning, and missing-value handling are common sources of silent failure.

| Provider and Access Path | Required event fields | Security identity | Invalid symbol | Currency in response | Additional event dates |
|---|---|---|---|---|---|
| Hang Seng (QVeris) | CN sample 2/2 | Returned security code matched the requested symbol | Handled correctly 3/3 | Not returned in this sample | Declaration, record, and payment dates |
| iFinD (Native MCP) | Missing single-event amount meaning and ex-dividend date | No response security code was available to cross-check | Handled correctly 3/3 | Not published in this sample | No single-event date set |
| Twelve Data (QVeris) | 3/3 | Published sample does not prove the response identified `AAPL` | Handled correctly 3/3 | `USD` | Only ex-dividend date in this sample |
| Alpha Vantage (QVeris) | 3/3 | Published sample does not prove the response identified `AAPL` | Handled correctly 3/3 | Not returned in this sample | Declaration, record, and payment dates |
| EODHD (QVeris) | 3/3 | Published sample does not prove the response identified `AAPL` | Handled correctly 3/3 | Not returned in this sample | Only ex-dividend date in this sample |
| Massive (QVeris) | 3/3 | Published sample does not prove the response identified `AAPL` | Handled correctly 3/3 | `USD` | Declaration, record, and payment dates |

Evaluate parameter clarity, schema stability, error recovery, pagination, identity provenance, and single-tool completion separately. The current Releases sufficiently observe required fields and invalid-symbol handling. Parameter clarity, pagination, and Agent Trial behavior remain unmeasured rather than being collapsed into a subjective score.

A symbol copied from the request cannot prove that the response belongs to the same security. Production validation should preserve the identifier returned by the provider and its mapping to the requested symbol. Likewise, correct invalid-symbol handling in three rounds says nothing about rate limits, timeouts, expired authentication, or server failures.

## Method, reproduction, and contribution

### How we tested

- **Positive samples:** `AAPL` for the US baseline paths and `600519.SH` for mainland China, with a frozen historical window.
- **Minimum contract:** verifiable security identity plus `effective_date` and a numeric, single-event cash `amount` per share.
- **Negative control:** an explicitly invalid symbol may produce an empty result or attributable provider rejection, but never a fabricated event.
- **Baseline repeatability:** three rounds per applicable case; Direct Test is mandatory.
- **Market extension:** one representative symbol for each of nine markets, with two rounds per applicable cell.
- **Evidence handling:** raw responses remain private by default; only sanitized, license-cleared terminal facts and digests are public.

Two market rounds measure repeatability for a deterministic API on a fixed sample; they do not establish complete market coverage. Explicitly unsupported markets are not probed again. A market cannot be marked not applicable merely because evidence is missing.

### No key required: replay the public Releases offline

Offline replay verifies the run plan, terminal cells, public terminals, suite fingerprint, and Release bytes. It proves that the publication has not been silently rewritten; it does not prove that a provider returns the same data today.

```bash
uv sync --locked --all-groups
uv run qveris-bench release replay releases/dividend-events-2026-q3-v1 \
  --expected-digest sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0
uv run qveris-bench release replay \
  releases/dividend-events-market-coverage-2026-q3-v1 \
  --expected-digest sha256:52f432c581fc6e8868e9070be21ad1b210b59238fb4c26d252f2a13a2d93f70e
```

Inspect the [baseline Release](../../releases/dividend-events-2026-q3-v1/release.json), [market Release](../../releases/dividend-events-market-coverage-2026-q3-v1/release.json), [Selection Snapshot](capability-seo/best-dividend-apis/selection-snapshot.json), [baseline public evidence](../../evidence/dividend-events-2026-q3-v1/), [market public evidence](../../evidence/dividend-events-market-coverage-2026-q3-v1/), and [offline replay guide](../release-replay.md). Every green or orange market cell can be traced by digest to its public terminal.

If you are integrating these results into an Agent workflow, read [Capability Discovery for AI Agents](https://qveris.ai/guides/capability-discovery-ai-agents/) before choosing a Tool. For command-line reproduction, use the [QVeris CLI guide](https://qveris.ai/guides/qveris-cli/).

### With a key: rerun the live calls

The [Dividend Events live workflow](../../.github/workflows/live-dividend-events-e2e.yml) runs three baseline rounds. The [Market workflow](../../.github/workflows/live-dividend-market-coverage-e2e.yml) runs two rounds for each applicable market binding:

- five QVeris Access Paths use `QVERIS_API_KEY`;
- iFinD uses only `IFIND_MCP_API_KEY` through its Native MCP;
- credentials must come from environment variables or GitHub Actions secrets, never fixtures, logs, Issues, or PRs.

A new live run does not overwrite a historical Release. Changes to inputs, rules, or outcomes produce a new version that preserves the previous digest.

### How providers and developers can participate

Providers can submit a [Provider submission](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=provider-submission.yml) describing the Provider, Access Path, official interface, authorization scope, and requested capability. API keys and private responses must not appear in an Issue or PR; credentials are handled through a secure channel.

Developers can propose [CAP methods and cases](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=cap-method-proposal.yml), including boundary cases, negative controls, field rules, and licensable sources. To dispute a result, file a [Result challenge](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=result-challenge.yml) with the Release digest and counter-evidence. Providers may correct facts but cannot purchase inclusion, conclusions, or ranking.

## Limitations, disclosures, and corrections

- This article tests only Dividend Events, not a provider's overall financial-data quality.
- Baseline samples cover only `AAPL`, `600519.SH`, and an invalid symbol; each market extension uses one representative symbol.
- `2/2` and `3/3` are fixed-sample repeatability, not full-universe coverage or a statistical confidence interval.
- Explicitly inapplicable markets were not called again; unknown states, temporary failures, and missing evidence cannot be relabeled not applicable.
- QVeris gateway latency describes this Access Path sample and cannot be attributed to a provider's Native API.
- QVeris credits are the public Inspect prices observed on August 12, 2026; discounted test-account charges are excluded from the comparison.
- Native plans come from official provider pages. Before procurement, verify quotas, real-time access, exchange fees, caching, and redistribution rights.
- QVeris operates some tested Access Paths, but the rules, terminal evidence, and reproduction entry points are public. This article does not accept paid ranking.
- Hang Seng's representative CN sample was 2/2. This does not establish support for every mainland China security or historical interval.

The public evidence, test rules, and reproduction entry points are available in [QVeris Capability Benchmarks](https://github.com/QVerisAI/qveris-capability-benchmarks).

## FAQ

### Which dividend API is best for developers?

There is no context-free winner. For a US ex-dividend date and single-event amount, reproduce the tested QVeris Access Paths for Twelve Data, Alpha Vantage, EODHD, and Massive first. Among the US samples, Alpha Vantage and Massive exposed the fuller date sets. For explicit currency, start with Twelve Data or Massive.

### Does “sample passed” mean the data is completely reliable?

No. It means only that the frozen symbol, time window, and rounds completed the current Dividend Event task. Full historical coverage, all securities, and continuous SLA require separate evidence.

### Does `0/2` mean the provider does not support that market?

No. It means the selected representative symbol did not produce a valid event in either fixed-window round. Possible causes include true lack of coverage, a different symbol dialect, permissions, or window-specific behavior. We use “not applicable” only when an official or Access Path contract says so explicitly.

### Why did iFinD not pass if it returned an annual cumulative dividend?

This CAP measures a single Dividend Event. An annual cumulative per-unit dividend neither establishes one event's amount nor supplies its ex-dividend date, so it is unsafe for ex-date backtests, price adjustment, and event notifications.

### Can I compare the latency values directly?

Use them only to prioritize reproduction within the same QVeris gateway boundary and observation window. A six-call median is not a Native API performance ranking or SLA. Production selection should measure P95/P99 under your target region and concurrency.

### Can I reproduce the test with my own API key?

Yes. QVeris-integrated providers use one `QVERIS_API_KEY`; iFinD uses its own Native MCP key. Keep the same inputs, rules, and round counts, and publish a new Release if results change instead of overwriting old evidence. Start with the [public repository](https://github.com/QVerisAI/qveris-capability-benchmarks), replay the Releases offline, then rerun the live workflow before committing to a provider.
