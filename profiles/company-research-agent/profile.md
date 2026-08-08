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
  - {"completed": 0, "provider_negative": 3, "rounds": 3}
- case:invalid-period:outcome: measured (3 evidence refs)
  - {"completed": 3, "provider_negative": 0, "rounds": 3}
- latency: evidence_insufficient
- cost: evidence_insufficient
- reliability: evidence_insufficient
- agent-interface: evidence_insufficient

## sec-filing-evidence
- case:aapl-risk-factor:outcome: measured (3 evidence refs)
  - {"completed": 0, "provider_negative": 3, "rounds": 3}
- case:invalid-filing-type:outcome: measured (3 evidence refs)
  - {"completed": 0, "provider_negative": 3, "rounds": 3}
- latency: evidence_insufficient
- cost: evidence_insufficient
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
- FMP income statement completed 15 of 18 Direct cells including the AAPL FY2025 revenue, invalid-period negative control, canonical-identifier, fiscal-period-shape, and agent-contract cases.
- The CN market-coverage case (600519.SH FY2020 revenue) returned provider_negative (fiscal_year_unavailable / empty_or_partial_data) in all three rounds; FMP did not expose the fact for the canonical SSE security under the frozen contract.
- This release records per-path terminal outcomes only; it contains no provider total, ranking, or Agent-friendly composite result.
- The included Massive Stocks risk-factor path returned unexpected response shapes in every Direct round; no cell satisfied the SEC evidence contract in this cycle, and the connector path should be re-qualified before reuse.
- FMP 10-K JSON and SEC filings search connector paths were terminally excluded after message-only probe responses; this release records the single-path cohort.
- All AAPL quote and freshness Direct observations were terminal provider_negative: Finnhub quote timestamps were stale beyond the frozen 15-minute window and EODHD timestamps were invalid at execution time.
- Neither included path (Finnhub or EODHD via QVeris) returned an SSE quote for the canonical security 600519.SH; all CN coverage and canonical agent-contract cells were provider_negative (unavailable_quote).

> No provider total, ranking, or Agent-friendly composite score is included.
