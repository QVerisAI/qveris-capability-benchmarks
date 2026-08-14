---
name: cap-article-writer
description: Use when writing or refreshing an evidence-backed CAP comparison article from a frozen writer-input.json, especially when the article must match the Dividend Golden CAP's decision value without allowing the model to invent facts, identities, numbers, or links.
---

# CAP Article Writer

Turn a frozen `writer-input.json` into a structured `editorial.json`. Treat the model as an editor, never as a fact source.

## Workflow

1. Read all of `writer-input.json` before drafting.
2. Read [article-blueprint.md](references/article-blueprint.md), [evidence-language.md](references/evidence-language.md), and [editorial-contract.md](references/editorial-contract.md).
3. Identify the reader decisions supported by the fact catalog. Keep Provider and Access Path scoped together.
4. Draft `editorial.json` only. Do not draft the final Markdown article.
5. Cite one or more valid `fact_refs` in every prose block.
6. Select Provider × Access Path identities only through a supported `decision_type`, structured `recommended_access_path_ids`, and `access_path_id` fields. The validator must be able to derive the same shortlist from frozen facts.
7. Leave every number, date, digest, URL, price, latency, market fraction, Provider name, and chart path to the deterministic renderer.
8. Validate the draft with the repository's article build or publication reproduce command.
9. Ask the human/editorial gate to approve the prose digest in the Publication Profile. Do not treat this approval as empirical evidence.
10. Compare the rendered article against [golden-rubric.md](references/golden-rubric.md). Revise and re-approve the editorial draft if any reader-value requirement is missing.

## Non-negotiable boundaries

- Never infer support from Provider marketing or an unobserved market.
- Never merge Native and QVeris Access Paths.
- Never declare an overall winner or invent a composite score.
- Never turn `provider_negative` into permanent non-support.
- Never turn `evidence_insufficient` into failure or support.
- Never write quantitative literals, URLs, digests, or Provider names in editorial prose.
- Never read private raw evidence. Use only the frozen writer input.

The final article is assembled by code from locked facts, tables, charts, reproduction commands, and this constrained editorial layer.
