# Operator runbook

## Create a formal CAP Pack

1. Run the protected `harbor-catalog-export` workflow or export the catalog locally
   with `QVERIS_HARBOR_EXPLORE_KEY`.
2. Keep `.harbor-snapshots/catalog/` private. Select a contract from its
   `contracts.json` and copy its catalog and contract digests from `meta.json`.
3. Create the CAP Pack with that exact Harbor provenance and freeze it with:

   ```bash
   uv run qveris-bench suite freeze cap_packs/<cap>/suite.yaml \
     --harbor-contracts .harbor-snapshots/catalog/contracts.json
   ```

4. Run Direct Tests for each included Provider × Access Path and publish only
   sanitized, digest-bound public evidence with the immutable release.

## Verify a published release

Published releases are replayed without credentials or provider calls:

```bash
uv run qveris-bench release replay releases/<published-harbor-cap-release>
```

The command validates frozen inputs, terminal cells, public evidence, and release
bytes. It is an offline verification, not a live rerun.
