# Harbor Reuse Architecture

**Status:** Accepted
**Date:** 2026-08-08

## Context

Harbor is the authoritative source for formal CAP contracts. Its code, internal
schemas, and contract payloads are private and must not be redistributed through
this public benchmark repository.

## Decision

Reuse Harbor through a protected, offline contract export, not as a code dependency
and not as a runtime service.

- The protected exporter reads Harbor Explore v2 and writes `contracts.json` plus
  metadata to private storage. It fails if any catalog contract cannot be read.
- The snapshot lives outside Git (`.harbor-snapshots/` is ignored). It is never an
  Actions artifact in this public repository.
- A formal CAP records the Harbor capability ID, contract version, snapshot digest,
  and contract digest; no CAP may be created from an unverified local idea.

## Responsibilities

| Owner | Owns | Does not own |
|---|---|---|
| Harbor (closed source) | Formal CAP contract truth | Benchmark conclusions, question judging, releases |
| Benchmark platform | Questions, judging rules, Direct/Agent evidence, immutable releases | Harbor contract authoring |
| Protected exporter | Harbor Explore contracts to private snapshot metadata | Evaluation logic |

## Guardrails

- No Harbor code, internal schema, raw contract, DB dump, or Actions artifact is
  committed or uploaded from this public repository.
- The snapshot is not a runtime dependency: benchmark runs and releases never query
  Harbor and never depend on its availability or cache state.
- Snapshot freshness is operator-driven: refresh, review the private diff, and pin
  new digests before creating a successor CAP or release.

## Operations

```bash
QVERIS_HARBOR_EXPLORE_KEY=... \
  uv run python scripts/export_harbor_catalog.py \
  --output .harbor-snapshots/catalog
```

Run this only in a protected environment or on an authorized operator machine.
The digest, not the file, enters public artifacts.
