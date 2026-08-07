# CAP Question Bank

`question_bank/` is the reviewed intake layer for future CAPs. It holds atomic,
QVeris-authored questions before they become executable CAP Packs. These questions
are the measurement candidates that a product-facing `DeveloperScenario` may
reference; they are not themselves end-to-end financial workflows.

## Selection rules

- A question has exactly one `cap_id`, explicit completion conditions, and required
  observations. It must test a business capability rather than a provider brand.
- Each CAP has at least one `core_positive` and one `boundary_negative` question.
  Additional role-labelled questions may test coverage, freshness and precision,
  response completeness, or the single-tool Agent contract. A role is not a score.
- A P0 scenario question declares market, language, as-of semantics, authoritative
  reference and tolerance rules, interface expectations, and the developer-selection
  implication before it can be promoted to an executable case.
- `sources.yaml` records only public, citable evidence. Official API documentation
  is marked `official_api`; public research benchmarks are marked
  `external_benchmark`.
- External benchmarks inform capability discovery and citation only. Their task text
  is not copied. Every bank question declares `text_origin: qveris_curated`.
- Questions reference an exact `(scenario_id, version)`. A scenario counts only its
  own attached questions toward required roles, and every attached question must
  measure a CAP required by that scenario.
- Repository-backed benchmark sources pin a full commit and source artifact or task
  identifiers. An external benchmark cannot be the sole authoritative truth source
  for a P0 evaluation contract.

## Lifecycle boundary

`runnable` means the capability already has an executable `cap_packs/<cap>/cap.yaml`.
`candidate` means it is deliberately not executable yet: it cannot be passed to the
suite compiler or treated as a provider benchmark result. Promoting a candidate
requires the normal CAP Pack definition, provider qualification, Direct Test, and
release gates.

## Review

Run `uv run qveris-bench question validate` after any bank edit. It rejects unknown
sources, scenarios, or CAPs, duplicate IDs, missing required question roles,
incomplete P0 evaluation contracts, and a lifecycle label that conflicts with an
executable CAP Pack.
