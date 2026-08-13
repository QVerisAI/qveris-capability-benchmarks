# Adding a CAP

A CAP Pack owns capability semantics; Core remains capability-agnostic.

1. Copy `cap_packs/_template/` into a new versioned CAP Pack.
2. Define business use, source provenance, valid and negative-control cases,
   observation schema, categorical outcome rules, and frozen suite.
3. Bind only terminally qualified Access Paths and make Direct Test mandatory.
4. Put response interpretation in a CAP-specific extractor; test malformed,
   stale, and negative responses before changing shared transport.
5. Compile with `qveris-bench suite freeze cap_packs/<cap>/suite.yaml`, then
   build and independently verify a release before publication.

## Adding a Publication Package

Publication is a separate CAP-owned projection over immutable Release facts:

1. Pin the Release plus every frozen contract and binding input by repository path
   and SHA-256. Current provider pricing is a publication-edition supplement, not
   part of the historical execution contract.
2. Build a typed CAP-owned Selection Snapshot. Keep Provider and Access Path as
   separate identities and make any qualification decision derivable from scoped
   case outcomes.
3. Render only decision-useful charts from the snapshot. Bind the structured chart
   data and committed image digest; do not assume PNG bytes are cross-platform.
4. Implement a `qveris_bench.publication_adapters` entry point that checks the exact
   Release topology, fresh snapshot bytes, chart data, material prose, SEO metadata,
   and an explicit external-link allowlist.
5. Add mutation tests for every buyer-facing claim and a wheel E2E that runs from
   outside the repository with no credentials and a clean HOME.

The deterministic package must work before adding model-assisted prose generation.
An AI model may propose text, but it cannot create measured facts or bypass the
offline publication validator.

An eligible Agent Trial exposes exactly one predetermined canonical tool. It
cannot discover, route, or select tools.
