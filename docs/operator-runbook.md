# Operator runbook

Use this runbook to validate a published benchmark release without access to
private raw artifacts or credentials.

## Replay a release

1. Check out the exact release commit and run `uv sync --locked --all-groups`.
2. Run `uv run qveris-bench schema export --check`.
3. Run `uv run qveris-bench suite freeze CAP_PACK/suite.yaml --output
   /tmp/frozen-suite.json` and inspect the resulting fingerprint.
4. Run `uv run qveris-bench suite plan CAP_PACK/suite.yaml --output
   /tmp/run-plan.json` to inspect the planned call count.
5. Run `uv run qveris-bench release verify RELEASE.json --digest DIGEST`.
6. Rebuild from the published release manifest, terminal cells, and authorized
   public evidence, then compare its digest.
7. Run the quality commands in `CONTRIBUTING.md`.

A replay must not invoke provider APIs, MCP servers, or an Agent backend.
credential values remain outside this repository and must never be added to a
release input, shell history, or support ticket.

## Live execution

Live workflows are manual, input-free, and use only the protected
`benchmark-e2e` environment. Before a live run, announce the fixed binding IDs,
call count, and credential names. Do not substitute a personal provider key for
a QVeris-controlled path. Preserve raw artifacts outside the checkout and only
publish validated, redacted evidence.

## Incident handling

If a replay digest differs, retain the inputs and report the mismatch. Do not
rewrite a published release, regenerate private evidence, or infer a provider
conclusion from a transport status.
