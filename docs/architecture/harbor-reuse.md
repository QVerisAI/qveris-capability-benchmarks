# Harbor Reuse Architecture

**Status:** Accepted
**Date:** 2026-08-08

## Context

Harbor is the authoritative source for formal CAP contracts. Harbor code remains
private; its exported catalog and contracts are intentionally public, versioned
benchmark inputs in this repository.

## Decision

Reuse Harbor through a versioned contract export, not as a code dependency and not
as a runtime service.

- The exporter reads Harbor Explore v2 and writes `harbor_catalog/contracts.json`
  plus metadata. It fails if any catalog contract cannot be read.
- The catalog, contracts, and metadata are committed together and are the public
  source of truth for formal CAP provenance.
- A formal CAP records the Harbor capability ID, contract version, snapshot digest,
  and contract digest; no CAP may be created from an unverified local idea.

## Responsibilities

| Owner | Owns | Does not own |
|---|---|---|
| Harbor (closed source) | Formal CAP contract truth | Benchmark conclusions, question judging, releases |
| Benchmark platform | Questions, judging rules, Direct/Agent evidence, immutable releases | Harbor contract authoring |
| Exporter | Harbor Explore contracts to versioned catalog metadata | Evaluation logic |

## Guardrails

- No Harbor code, credentials, DB dump, or unreviewed Actions artifact is committed
  or uploaded from this public repository. Authorized contract exports are versioned
  under `harbor_catalog/`.
- The snapshot is not a runtime dependency: benchmark runs and releases never query
  Harbor and never depend on its availability or cache state.
- Snapshot freshness is operator-driven: refresh, review the public diff, and pin
  new digests before creating a successor CAP or release.

## Operations

```bash
QVERIS_HARBOR_EXPLORE_KEY=... \
  uv run python scripts/export_harbor_catalog.py \
  --output harbor_catalog
```

Review and commit the three generated files together. The digests enter every
formal CAP and release that uses the contract.
