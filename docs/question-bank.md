# CAP Question Bank

`question_bank/` is the reviewed intake layer for future CAPs. It holds atomic,
QVeris-authored questions before they become executable CAP Packs. These questions
are the measurement candidates that a product-facing Financial Task may later
reference; they are not themselves end-to-end financial workflows.

## Selection rules

- A question has exactly one `cap_id`, explicit completion conditions, and required
  observations. It must test a business capability rather than a provider brand.
- Each CAP has one positive task and one negative control. This keeps usefulness and
  safe failure behavior together from the first review.
- `sources.yaml` records only public, citable evidence. Official API documentation
  is marked `official_api`; public research benchmarks are marked
  `external_benchmark`.
- External benchmarks inform capability discovery and citation only. Their task text
  is not copied. Every bank question declares `text_origin: qveris_curated`.

## Lifecycle boundary

`runnable` means the capability already has an executable `cap_packs/<cap>/cap.yaml`.
`candidate` means it is deliberately not executable yet: it cannot be passed to the
suite compiler or treated as a provider benchmark result. Promoting a candidate
requires the normal CAP Pack definition, provider qualification, Direct Test, and
release gates.

## Review

Run `uv run qveris-bench question validate` after any bank edit. It rejects unknown
sources or CAPs, duplicate IDs, incomplete positive/negative coverage, and a
lifecycle label that conflicts with an executable CAP Pack.
