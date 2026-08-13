# CAP Question Bank

`question_bank/` is the reviewed intake layer for future CAPs. It holds atomic,
Harbor-derived, QVeris-authored questions before they become executable CAP Packs.
These questions are not themselves end-to-end financial workflows.

## Selection rules

- A question has exactly one `cap_id`, explicit completion conditions, and required
  observations. It must test a business capability rather than a provider brand.
- Each CAP has at least one `core_positive` and one `boundary_negative` question.
  Additional role-labelled questions may test coverage, freshness and precision,
  response completeness, or the single-tool Agent contract. A role is not a score.
- The full question lifecycle and pass rules live in the [question evaluation
  model](question-evaluation-model.md): origins are citation-only, judgment is per
  run cell, and released facts are `measured`, `declared`, or
  `evidence_insufficient`.
- `sources.yaml` records the public Harbor catalog citation. Every candidate
  capability maps to one Harbor capability ID, and every bank question declares
  `text_origin: qveris_curated`.

## Lifecycle boundary

`runnable` means the capability already has an executable `cap_packs/<cap>/cap.yaml`.
`candidate` means it is deliberately not executable yet: it cannot be passed to the
suite compiler or treated as a provider benchmark result. Promoting a candidate
requires the normal CAP Pack definition, provider qualification, Direct Test, and
release gates.

## Review

Run `uv run qveris-bench question validate` after any bank edit. It rejects unknown
sources or CAPs, duplicate IDs, missing required question roles, a non-Harbor CAP
source, and a lifecycle label that conflicts with an executable CAP Pack.
