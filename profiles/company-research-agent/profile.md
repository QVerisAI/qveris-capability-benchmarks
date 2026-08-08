# company-research-agent-profile-v1 — Task Fit Profile

- scenario: company-research-agent@1.1.0
- profile version: 1.0.0

## financial-statement-facts
- case:aapl-agent-contract:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- case:aapl-canonical-identifier:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- case:aapl-fiscal-period-shape:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- case:aapl-revenue-fy2025:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- case:cn-600519-market-coverage:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- case:invalid-period:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- latency: measured (18 evidence refs)
  - {"cells": 18, "max_ms": 2457.57, "measurement_boundary": "qveris_gateway", "median_ms": 1569.8000000000002, "min_ms": 1077.92, "unit": "ms"}
- cost: measured (18 evidence refs)
  - {"cells": 18, "measurement_boundary": "qveris_gateway", "median_credits": 2.42, "total_credits": 43.56, "unit": "credits"}
- reliability: evidence_insufficient
- agent-interface: evidence_insufficient

## sec-filing-evidence
- case:aapl-agent-contract:outcome: measured (3 evidence refs)
  - {"completed": 2, "provider_negative": 1, "rounds": 3}
- case:aapl-risk-factor:outcome: measured (3 evidence refs)
  - {"completed": 0, "provider_negative": 3, "rounds": 3}
- case:aapl-us-market-coverage:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- case:cik-canonical-identifier:outcome: measured (3 evidence refs)
  - {"completed": 0, "provider_negative": 3, "rounds": 3}
- case:invalid-filing-type:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- latency: measured (15 evidence refs)
  - {"cells": 15, "max_ms": 2495.13, "measurement_boundary": "qveris_gateway", "median_ms": 880.68, "min_ms": 735.26, "unit": "ms"}
- cost: measured (5 evidence refs)
  - {"cells": 5, "measurement_boundary": "qveris_gateway", "median_credits": 0.1, "total_credits": 0.5, "unit": "credits"}
- reliability: evidence_insufficient
- agent-interface: evidence_insufficient

## stock-quote
- case:aapl-freshness-precision:outcome: measured (6 evidence refs)
  - {"completed": 0, "provider_negative": 6, "rounds": 6}
- case:aapl-quote:outcome: measured (6 evidence refs)
  - {"completed": 0, "provider_negative": 6, "rounds": 6}
- case:cn-600519-agent-contract:outcome: measured (6 evidence refs)
  - {"completed": 0, "provider_negative": 6, "rounds": 6}
- case:cn-600519-market-coverage:outcome: measured (6 evidence refs)
  - {"completed": 0, "provider_negative": 6, "rounds": 6}
- case:invalid-stock:outcome: measured (6 evidence refs)
  - {"completed": 6, "provider_negative": 0, "rounds": 6}
- latency: evidence_insufficient
- cost: evidence_insufficient
- reliability: evidence_insufficient
- agent-interface: evidence_insufficient

## Limitations
- The included FMP income-statement path completed all six Direct cases across three rounds (18 cells): FY2025 AAPL revenue, the invalid-period negative control, the CN 600519 market-coverage case (resolved to the 600519.SS dialect with 10 years of history), canonical-identifier resolution, fiscal-period shape, and the fixed-tool agent contract.
- Latency and cost are QVeris gateway-side observations (elapsed_time_ms and cost credits from the QVeris API response), including gateway routing, forwarding, and QVeris billing; they are not FMP native API latency or pricing.
- The as-reported income-statement connector was re-qualified to the standard income-statement tool after it left QVeris discovery; Alpha Vantage income statement and the official SEC company facts connector paths remain terminally excluded after message-only probe responses.
- This release records per-path terminal outcomes only; it contains no provider total, ranking, or Agent-friendly composite result.
- The included Massive Stocks risk-factor path completed 6 of 15 Direct cells; 8 cells recorded provider-side filing_unavailable because the connector intermittently returns an explicit error envelope (those calls return no cost from the gateway), and the negative control recorded filing_type_not_supported because the endpoint has no filing-type parameter.
- Latency and cost are QVeris gateway-side observations (elapsed_time_ms and cost credits from the QVeris API response), including gateway routing, forwarding, and QVeris billing; they are not Massive native API latency or pricing.
- The FMP 10-K JSON and SEC filings search connectors were terminally excluded after message-only error responses for both parameter forms; this release records the single-path cohort.
- All AAPL quote and freshness Direct observations were terminal provider_negative: Finnhub quote timestamps were stale beyond the frozen 15-minute window and EODHD timestamps were invalid at execution time.
- Neither included path (Finnhub or EODHD via QVeris) returned an SSE quote for the canonical security 600519.SH; all CN coverage and canonical agent-contract cells were provider_negative (unavailable_quote).

> No provider total, ranking, or Agent-friendly composite score is included.
