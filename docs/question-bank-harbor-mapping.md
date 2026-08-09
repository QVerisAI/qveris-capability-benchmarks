# Question Bank ← Harbor CAP Catalog Mapping

The question bank exists to help a developer choose the provider and Access
Path for a concrete financial product task. Every question must therefore be
strongly correlated with the CAP it measures and cite an authoritative source
for the CAP's input and output contract. The canonical source is the Harbor
explore v2 catalog (`https://harbor.qveris.cloud/api/v2/explore/catalog`),
which publishes every active CAP with its `standard_query`, `field_spec`,
`scope`, `output_cardinality`, and `row_key`.

## Selection rules

1. Start from the Harbor catalog's full inventory (161 CAPs).
2. First batch = CAPs with `coverage: full` and `provider_count >= 3` (57 CAPs
   listed below). These have enough suppliers to make vendor selection
   meaningful.
3. Each CAP gets at least one `core_positive` and one `boundary_negative`
   question. Question inputs are derived from the CAP contract's
   `standard_query.required` fields; required observations come from
   `field_spec.required`; boundary questions exercise the contract's explicit
   negative states (invalid identifier, missing required combination,
   unsupported market).
4. Every question cites `harbor-capability-catalog` as its source and keeps
   `text_origin: qveris_curated`. Nothing is copied from external benchmarks.
5. New CAPs enter the bank as `candidate` until an executable CAP Pack,
   provider qualification, and release evidence exist.

## Covered CAP inventory (full coverage, provider_count >= 3)

| Harbor CAP ID | Name | Domain | Coverage | Providers |
|---|---|---|---|---|
| ANALYTICS.ATR | 平均真实波幅 | ANALYTICS | full | 3 |
| ANALYTICS.BBANDS | 布林带 | ANALYTICS | full | 3 |
| ANALYTICS.CCI | 顺势指标 | ANALYTICS | full | 3 |
| ANALYTICS.EMA | 指数移动平均 | ANALYTICS | full | 4 |
| ANALYTICS.MACD | 平滑异同移动平均 | ANALYTICS | full | 4 |
| ANALYTICS.RSI | 相对强弱指标 | ANALYTICS | full | 4 |
| ANALYTICS.SMA | 简单移动平均 | ANALYTICS | full | 4 |
| ANALYTICS.STOCH | 随机指标 | ANALYTICS | full | 3 |
| ANALYTICS.TECH_INDICATORS | Technical Indicators | ANALYTICS | full | 4 |
| CRYPTO.BARS.HISTORY | Crypto Historical Bars | CRYPTO | full | 5 |
| CRYPTO.MARKET_RANKINGS | Crypto Market Rankings | CRYPTO | full | 4 |
| CRYPTO.REF_MASTER | Crypto Asset Master | CRYPTO | full | 4 |
| CRYPTO.SPOT.RT | Crypto Real-time Quotes | CRYPTO | full | 5 |
| ESG.CONTROVERSY | ESG Controversies | ESG | full | 5 |
| ETF.REF_MASTER | ETF Reference Master | ETF | full | 6 |
| EVENT.CALENDAR.CORP | Corporate Event Calendar | EVENT | full | 5 |
| FLOW.LARGE_ORDER | Stock Capital Flow | FLOW | full | 3 |
| FLOW.SECTOR.CAPITAL | Sector Capital Flow | FLOW | full | 3 |
| FUND.MUTUAL.NAV | Mutual Fund NAV | FUND | full | 4 |
| FUNDAMENTALS.BS | Balance Sheet | FUNDAMENTALS | full | 4 |
| FUNDAMENTALS.CF | Cash Flow Statement | FUNDAMENTALS | full | 3 |
| FUNDAMENTALS.DERIVED_RATIOS | Financial Ratios & Valuation | FUNDAMENTALS | full | 5 |
| FUNDAMENTALS.IS | Income Statement | FUNDAMENTALS | full | 3 |
| FX.SPOT | FX Spot Rates | RATES | full | 4 |
| MKT.AFTER_HOURS | Pre/Post-Market Quotes | MKT | full | 4 |
| MKT.BARS.ADJUSTED | Split & Dividend Adjusted Prices | MKT | full | 4 |
| MKT.BARS.EOD | End-of-Day OHLCV Bars | MKT | full | 3 |
| MKT.BARS.INTRADAY | Intraday OHLCV Bars | MKT | full | 3 |
| MKT.BREADTH.INTERNALS | Market Breadth Internals | MKT | full | 3 |
| MKT.CN.BONUS | Bonus & Dividend Plans | MKT | full | 4 |
| MKT.CORPORATE_ACTIONS | Corporate Actions | MKT | full | 8 |
| MKT.DIVIDENDS | 分红事件 | MKT | full | 6 |
| MKT.L1.RT | Real-time Level 1 Quotes | MKT | full | 5 |
| MKT.SPLITS | 拆股事件 | MKT | full | 3 |
| MKT.TRADING.AGGREGATE | Market Trading Statistics | MKT | full | 5 |
| NEWS.DEDUP.CLUSTER | News Deduplication & Clustering | NEWS | full | 7 |
| NEWS.FIN.REALTIME | Real-time Financial News | NEWS | full | 8 |
| NEWS.FIN.TAGGED | Tagged News with Sentiment | NEWS | full | 10 |
| NON_FIN.SOCIAL_MEDIA | Social Media Monitoring | NON_FIN | full | 6 |
| NON_FIN.WEB_SCRAPE | Web Scraping | NON_FIN | full | 5 |
| NON_FIN.YOUTUBE_TRANSCRIPT | YouTube Video Transcripts | NON_FIN | full | 3 |
| NON_FIN.YOUTUBE_TRANSCRIPT_URL | YouTube 字幕链接 | NON_FIN | full | 3 |
| OWNERSHIP.INSIDER_TRADES | Insider Trades | OWNERSHIP | full | 3 |
| OWNERSHIP.INSTITUTIONAL | Institutional Holdings | OWNERSHIP | full | 3 |
| OWNERSHIP.SHARE_STRUCTURE | Share Structure | OWNERSHIP | full | 5 |
| OWNERSHIP.SHORT_INTEREST | Short Interest | OWNERSHIP | full | 3 |
| RATES.GOVT_BENCHMARK | Government Bond Yields | RATES | full | 3 |
| REF.CLASSIFICATION.INDUSTRY | Industry Classification | REF | full | 10 |
| REF.COMPANY_PROFILE | Company Profile | REF | full | 4 |
| REF.COUNTRY_REGION_MAP | Country & Region Mapping | REF | full | 4 |
| REF.CURRENCY_MASTER | Currency Master | REF | full | 3 |
| REF.ENTITY_MASTER | Legal Entity Master | REF | full | 9 |
| REF.ENTITY_RELATIONSHIP | Entity Relationships | REF | full | 3 |
| REF.HALT_EVENTS | 停牌事件 | REF | full | 3 |
| REF.SYMBOLOGY | Identifier Symbology Mapping | REF | full | 3 |
| RESEARCH.ANALYST_REPORTS | Analyst Research Reports | RESEARCH | full | 7 |
| SENTIMENT.TEXT_SIGNALS | News Text Signal | SENTIMENT | full | 9 |

## First batch added to the bank

| Bank capability | Harbor CAP ID | Rationale |
|---|---|---|
| `realtime-financial-news` | NEWS.FIN.REALTIME | 8 providers; contract requires symbol-or-query and timestamps |
| `dividend-events` | MKT.DIVIDENDS | 6 providers; dated event contract with per-share amount |
| `crypto-spot-quote` | CRYPTO.SPOT.RT | 5 providers; global market, price plus OHLC fields |
| `financial-ratios` | FUNDAMENTALS.DERIVED_RATIOS | 5 providers; pe_ttm, market_cap, as_of_date contract |
| `fx-spot-rate` | FX.SPOT | 4 providers; pair symbol and spot price contract |
| `govt-bond-yield` | RATES.GOVT_BENCHMARK | 3 providers; country/tenor dated close contract |

## Next batches

The remaining 51 covered CAPs above are the pipeline. Batch priority follows
provider_count and developer-selection relevance (quote, reference, news, and
fundamental CAPs first), then extends to `coverage: good` and lower-provider
CAPs only when a bank question adds selection signal without duplicating an
existing capability.
