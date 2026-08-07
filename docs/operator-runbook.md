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
5. Verify the immutable release with `uv run qveris-bench release verify
   releases/etf-holdings-2026-q3-v1/release.json --digest
   sha256:62df52047ecb0bcf66fce96a0240f97f29c1bc9e55066ca9e06ae0f878d00c0f`.
6. Run the local quality commands in `CONTRIBUTING.md` before reporting a result.

If a digest differs, preserve the inputs and report the mismatch. Do not modify
a published release, regenerate private evidence, or infer a provider conclusion
from a transport status.

## Fixed live workflows

Live workflows are manually dispatched, input-free, and use only the protected
`benchmark-e2e` environment. Before dispatch, announce the frozen binding IDs,
call count, and credential *names*; do not substitute a personal provider key.

`Live Wind Native MCP E2E` is deliberately narrower: it invokes the single fixed
canonical tool `get_stock_price_indicators` against the registered Wind native
MCP path. Its `WIND_MCP_API_KEY` is exposed only as the workflow-local
`WIND_API_KEY`; it must never be printed, committed, reused for routing, or used
for another provider. Download only the workflow's sanitized terminal-evidence
artifact, never a raw response.

## Release limits

The published ETF release is structurally reproducible but currently records two
executed Direct access paths. It is not a substitute for the design's formal
5–8-provider ETF cohort. Keep that limitation in any operator report.
