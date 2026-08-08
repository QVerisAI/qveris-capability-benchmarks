# Operator runbook

This runbook verifies a published release without provider credentials or access
to private raw artifacts. A replay must never call a provider API, MCP server, or
Agent backend.

## Offline replay

1. Check out the exact release commit and run `uv sync --locked --all-groups`.
2. Run `uv run qveris-bench schema export --check`.
3. Freeze the CAP suite with `uv run qveris-bench suite freeze
   cap_packs/etf_holdings/suite.yaml --output /tmp/frozen-suite.json`.
4. Compile the same suite with `uv run qveris-bench suite plan
   cap_packs/etf_holdings/suite.yaml --output /tmp/run-plan.json`.
5. Verify every published release with `uv run qveris-bench release verify`:

   - `releases/etf-holdings-2026-q3-v1/release.json` —
     `sha256:62df52047ecb0bcf66fce96a0240f97f29c1bc9e55066ca9e06ae0f878d00c0f`
   - `releases/stock-quote-2026-q3-v2/release.json` —
     `sha256:7e7ff0ebf2c72e96e6bb1544c07da4195f82154378b686d544667b922d5a6e4b`
   - `releases/stock-quote-family-2026-q3-v1/release.json` —
     `sha256:2984a796bee2e9242c818f3336927972fe93030ca13f01f459e7333d5d509f57`
   - `releases/financial-statements-2026-q3-v1/release.json` —
     `sha256:a22d3dbcb47d094baac201a0c100e6ad87b6159d6780bdf29ea3c5f0e4a8abaf`
   - `releases/sec-filing-evidence-2026-q3-v1/release.json` —
     `sha256:5a159d6e5777b3829e57f861e18182a76540d94dc1f3b8c23ae4410207e5024e`
   - `releases/financial-statements-2026-q3-v2/release.json` —
     `sha256:9e797df8592ff139b9f09bcf69d88c5b7dc7664384210388f84e33329f0017b8`
   - `releases/sec-filing-evidence-2026-q3-v2/release.json` —
     `sha256:865ed24c2b3d3be72e8cd665421ad33f9fcceab1644b90e0868ff0c82a32d858`
   - `releases/financial-statements-2026-q3-v3/release.json` —
     `sha256:d191640f23fd1205874d8667f6f9d23ca5c8cfacd4c6aa97d4d73319df32297e`
   - `releases/sec-filing-evidence-2026-q3-v3/release.json` —
     `sha256:6faffeb8bf4fca0b8fa58bd9c2ba5d106fac47f99e730b6a99fb8138f59ee4cd`
6. Rebuild the Company Research Task Fit Profile with
   `uv run qveris-bench profile build --input profiles/company-research-agent.yaml
   --output-dir /tmp/profile-out` and confirm both outputs match the committed
   `profiles/company-research-agent/` files byte-for-byte.
7. Run the local quality commands in `CONTRIBUTING.md` before reporting a result.

If a digest differs, preserve the inputs and report the mismatch. Do not modify
a published release, regenerate private evidence, or infer a provider conclusion
from a transport status.

## Release attribution gate

New releases require every `provider_negative` cell to carry a provider-side
`failure_attribution` (`invalid_parameters`, `provider_validation_error`,
`provider_runtime_error`, `auth_or_entitlement`, `rate_limited`,
`network_or_timeout`, `empty_or_partial_data`, or `truncated_or_unpaged`).
Benchmark-side causes such as `response_interpretation_error`,
`benchmark_system_error`, `agent_output_error`, or `unknown` are not publishable
as `provider_negative`; re-qualify or exclude those paths instead. Historical
releases predate this gate and remain digest-verifiable via the replay steps
above.

## Fixed live workflows

Live workflows are manually dispatched, input-free, and use only the protected
`benchmark-e2e` environment. Before dispatch, announce the frozen binding IDs,
call count, and credential *names*; do not substitute a personal provider key.

`Live Wind Native MCP E2E` is deliberately narrower: it invokes the single fixed
canonical tool `get_stock_price_indicators` against its frozen Wind native MCP
endpoint and arguments. It is a fixed E2E contract, not a provider-registry
qualification. Its `WIND_MCP_API_KEY` is exposed only as the workflow-local
`WIND_API_KEY`; it must never be printed, committed, reused for routing, or used
for another provider. Download only the workflow's sanitized terminal-evidence
artifact, never a raw response.

## Release limits

The published ETF release records the two included Direct access paths. Its six
candidate providers each have a frozen terminal qualification: Alpha Vantage and
FIU are included; Twelve Data, Financial Modeling Prep, Finnhub, and EODHD are
excluded. Run every included path through all frozen rounds, but do not execute an
excluded path unless its qualification and authorization are changed first.
