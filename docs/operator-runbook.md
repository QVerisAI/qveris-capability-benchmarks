# Operator runbook

## Create a formal CAP Pack

1. Refresh the versioned `harbor_catalog/` directory with
   `QVERIS_HARBOR_EXPLORE_KEY`. The protected `harbor-catalog-export` workflow only
   detects upstream drift; it never publishes an unreviewed artifact. Review and
   commit the catalog, contracts, and metadata together.
2. Select a contract from `harbor_catalog/contracts.json` and copy its catalog and
   contract digests from `harbor_catalog/meta.json`.
3. Create the CAP Pack with that exact Harbor provenance and freeze it with:

   ```bash
   uv run qveris-bench suite freeze cap_packs/<cap>/suite.yaml \
     --harbor-contracts harbor_catalog/contracts.json
   ```

4. Run Direct Tests for each included Provider × Access Path and publish only
   sanitized, digest-bound public evidence with the immutable release.

## Verify a published release

Published releases are replayed without credentials or provider calls:

```bash
uv run qveris-bench release replay releases/<published-harbor-cap-release> \
  --harbor-contracts harbor_catalog/contracts.json
```

The command validates the public Harbor contract provenance, frozen inputs, terminal
cells, public evidence, and release bytes. It is an offline verification, not a
live rerun.
