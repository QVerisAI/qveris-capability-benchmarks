# Adding a CAP

A CAP Pack owns capability semantics; Core remains capability-agnostic.

1. Copy `cap_packs/_template/` into a new versioned CAP Pack.
2. Define business use, source provenance, valid and negative-control cases,
   observation schema, categorical outcome rules, and frozen suite.
3. Bind only terminally qualified Access Paths and make Direct Test mandatory.
4. Put response interpretation in a CAP-specific extractor; test malformed,
   stale, and negative responses before changing shared transport.
5. Compile with `qveris-bench suite freeze`, then build and independently verify
   a release before publication.

An eligible Agent Trial exposes exactly one predetermined canonical tool. It
cannot discover, route, or select tools.
