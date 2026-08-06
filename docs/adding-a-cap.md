# Adding a CAP

A CAP Pack owns capability semantics; Core remains capability-agnostic.

1. Copy `cap_packs/_template/` into a new versioned CAP Pack.
2. Define the business use, source provenance, valid and negative-control
   cases, observation schema, categorical outcome rules, and frozen suite.
3. Add provider bindings only for terminally qualified Access Paths.
4. Put response interpretation in a CAP-specific extractor and test malformed,
   stale, and negative responses before transport changes.
5. Compile the suite with `qveris-bench suite freeze` and verify that no Core
   schema, score field, or provider-total concept is required.
6. Add a release fixture and an independent replay check before publishing.

Direct Test is mandatory for each included path. An Agent Trial, when eligible,
has exactly one preselected canonical tool and cannot discover or route tools.
