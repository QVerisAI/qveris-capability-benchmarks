# Company Research Benchmark v2 — Handoff

- **Date:** 2026-08-08
- **Repository:** `QVerisAI/qveris-capability-benchmarks`
- **Base:** `master`

## Delivered

The Company Research Agent selection loop is complete end to end:

1. Question Bank v2 with `DeveloperScenario` contracts (company-research-agent
   1.0.0 / 1.1.0) and role-labelled question families.
2. Executable production CAP Packs:
   - `stock-quote-v3` (`cap_packs/stock_quote_family/`)
   - `financial-statements-v1` (`cap_packs/financial_statement_facts/`)
   - `sec-filing-evidence-v1` (`cap_packs/sec_filing_evidence/`)
3. Verified immutable releases:
   - `stock-quote-family-2026-q3-v1`
   - `financial-statements-2026-q3-v1`
   - `sec-filing-evidence-2026-q3-v1`
   - `financial-statements-2026-q3-v2`
   - `sec-filing-evidence-2026-q3-v2`
4. Deterministic Company Research Task Fit Profile v1 (`profiles/company-research-agent/`)
   with per-CAP case outcomes and honest `evidence_insufficient` dimensions; the
   profile now pins the FSF/SEC v2 releases.
5. Replay runbook covering all five published releases (`docs/operator-runbook.md`).

## Honest findings recorded in the releases

- Stock Quote: both included paths pass the invalid-symbol boundary control (6/6
  completed); all AAPL quote/freshness cells were provider_negative
  (stale/invalid timestamps); no included path returned an SSE quote for
  600519.SH (12/12 unavailable).
- Financial Statements v2: after the as-reported connector left QVeris discovery,
  the cohort was re-qualified to the standard FMP income-statement tool; all 18
  matrix cells (FY2025 AAPL revenue, invalid-period control, CN 600519 coverage,
  canonical identifier, fiscal-period shape, fixed-tool agent contract) are
  completed.
- SEC Filing Evidence v2: 6 of 15 cells completed; the Massive Stocks connector
  intermittently returns an explicit error envelope (8 cells recorded as
  provider-side `filing_unavailable`) and its endpoint has no filing-type
  parameter (negative control recorded as `filing_type_not_supported`). This is
  honest provider reliability evidence; no cell is a benchmark-side parse
  failure.

## Follow-ups (not blockers for v2)

- Re-qualify the excluded connector paths (sec-gov company facts, FMP 10-K JSON,
  FMP SEC filings search, Alpha Vantage income statement) when they expose
  working contracts; evidence digests are recorded in the provider registry.
- Re-probe the Massive risk-factor connector when its reliability improves; the
  recorded `filing_unavailable` cells should be re-run rather than re-qualified.
- Add latency / cost / reliability measurement contracts so the profile can move
  those dimensions from `evidence_insufficient` to `measured`.

## Replay

```bash
uv sync --locked --all-groups
uv run qveris-bench schema export --check
uv run qveris-bench release verify releases/<release>/release.json --digest <digest>
uv run qveris-bench profile build --input profiles/company-research-agent.yaml --output-dir /tmp/profile-out
uv run pytest -q
```

Digests and per-release limitations live in `releases/*/release-input.json`.
