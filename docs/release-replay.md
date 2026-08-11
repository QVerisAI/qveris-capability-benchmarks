# Offline release replay

Offline replay proves that the public files in one release directory are internally
consistent and deterministically rebuild the published `release.json` bytes. It
does not rerun a Provider and does not establish community reproduction.

## Quickstart

Check out the release commit and use Python 3.12 with the locked dependency set:

```bash
uv sync --locked --all-groups
uv run qveris-bench release replay releases/<release-id>
```

The command validates:

1. `release-input.json`, `run-plan.json`, `cells.json`, `evidence.json`, and
   `release.json` are present and schema-valid;
2. the raw run-plan digest and suite fingerprint match the release input;
3. planned and terminal cells have the same run keys and identities;
4. public evidence passes the historical release gates;
5. the rebuilt canonical bytes exactly equal the published release.

Replaying a release must not invoke
provider APIs, MCP servers, or an Agent backend. Raw artifacts and credential values remain outside
this repository. The command does not write into the release directory.

## Verify an external identity

Internal consistency alone cannot detect a coordinated edit to every file in a
checkout. Compare against a trusted digest published outside that checkout:

```bash
uv run qveris-bench release replay releases/<release-id> \
  --expected-digest sha256:<published-digest>
```

The expected digest authenticates the published bundle identity. It still does not
make provider calls. A maintainer rerun or community reproduction is a new live
execution with new evidence and environment disclosure.

## Failure handling

Replay fails closed on a missing or malformed file, plan digest mismatch, suite
fingerprint mismatch, cell topology change, evidence-gate failure, canonical byte
mismatch, or expected-digest mismatch. Preserve the checkout and open a Result
challenge through `CONTRIBUTING.md`; do not edit a historical release in place.
