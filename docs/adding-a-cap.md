# Adding a CAP

A CAP Pack owns capability semantics; Core remains capability-agnostic.

1. Select a real contract from the versioned `harbor_catalog/contracts.json`. Do
   not create a CAP Pack from a local idea or an external benchmark.
2. Copy `cap_packs/_template/` into a new versioned CAP Pack and record the
   Harbor capability ID, contract version, catalog digest, and contract digest.
3. Define business use, valid and negative-control cases,
   observation schema, categorical outcome rules, and frozen suite.
4. Bind only terminally qualified Access Paths and make Direct Test mandatory.
5. Put response interpretation in a CAP-specific extractor; test malformed,
   stale, and negative responses before changing shared transport.
6. Compile with `qveris-bench suite freeze cap_packs/<cap>/suite.yaml
   --harbor-contracts harbor_catalog/contracts.json`, then build and independently
   verify a release before publication.

An eligible Agent Trial exposes exactly one predetermined canonical tool. It
cannot discover, route, or select tools.
