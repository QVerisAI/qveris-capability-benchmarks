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
4. Deterministic Company Research Task Fit Profile v1 (`profiles/company-research-agent/`)
   with per-CAP case outcomes and honest `evidence_insufficient` dimensions.
5. Replay runbook covering all five published releases (`docs/operator-runbook.md`).

## Honest findings recorded in the releases

- Stock Quote: both included paths pass the invalid-symbol boundary control (6/6
  completed); all AAPL quote/freshness cells were provider_negative
  (stale/invalid timestamps); no included path returned an SSE quote for
  600519.SH (12/12 unavailable).
- Financial Statements: FMP completes the invalid-period control; AAPL FY2025
  revenue was provider_negative (invalid_revenue) in every round.
- SEC Filing Evidence: the Massive Stocks connector returned unexpected response
  shapes in every round; no cell satisfied the evidence contract this cycle.

## Follow-ups (not blockers for v2)

- Re-qualify the excluded connector paths (sec-gov company facts, FMP 10-K JSON,
  FMP SEC filings search, Alpha Vantage income statement) when they expose
  working contracts; evidence digests are recorded in the provider registry.
- Investigate the FMP as-reported FY2025 revenue schema for the
  `invalid_revenue` outcome.
- Add latency / cost / reliability measurement contracts so the profile can move
  those dimensions from `evidence_insufficient` to `measured`.
- Build the extended question roles (coverage/shape/agent-contract per CAP) from
  the question evaluation model.

## Replay

```bash
uv sync --locked --all-groups
uv run qveris-bench schema export --check
uv run qveris-bench release verify releases/<release>/release.json --digest <digest>
uv run qveris-bench profile build --input profiles/company-research-agent.yaml --output-dir /tmp/profile-out
uv run pytest -q
```

Digests and per-release limitations live in `releases/*/release-input.json`.
