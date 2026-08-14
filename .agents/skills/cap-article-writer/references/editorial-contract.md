# Editorial contract

Output one JSON object with these fields:

- `schema_version`: `1`
- `skill_id`: `cap-article-writer`
- `skill_version`: the Skill version used
- `lead`: copy block
- `decision_scenarios`: at least four scenario blocks with `heading`, `copy`, `recommended_access_path_ids`, and `fact_refs`
- `evidence_explainer`: copy block
- `cap_explainer`: copy block explaining why the capability contract is non-trivial without repeating evidence-state definitions
- `chart_explanations`: exactly `market` and `tradeoff` copy blocks
- `provider_analyses`: exactly one block per required Access Path, each with `access_path_id`, `copy`, and `fact_refs`
- `agent_notes`: copy block
- `limitations`: copy block
- `faq`: at least three entries with `question`, `answer`, and `fact_refs`

A copy block contains non-empty `copy` and non-empty `fact_refs`. Every reference must exist in `writer-input.json.fact_catalog`.

Do not put numbers, dates, URLs, digests, credits-per-call strings, Provider names, or Access Path names in free prose. Use “the selected path”, “this path”, or “the released cohort”; the renderer inserts exact identities and material values.
