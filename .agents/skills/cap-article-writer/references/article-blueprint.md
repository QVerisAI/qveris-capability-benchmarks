# Article blueprint

Write for a developer who wants to choose an Access Path, not for an internal benchmark reviewer.

Use this reader sequence:

1. Answer-first lead: define the capability, cohort, observation boundary, and the decisions the article can support.
2. Results at a glance: let locked tables state the facts; explain how to interpret the four evidence states.
3. How developers should choose: provide at least four distinct scenarios. Each scenario must have a structured Access Path selection and evidence-backed trade-off.
4. Evidence and Provider differences: use a dedicated `cap_explainer` to explain why the CAP is non-trivial and what the completion contract proves. Do not repeat the evidence-state definitions from Results at a glance.
5. Chart explanations: explain axes, cells, denominators, observation scope, and why the chart changes a decision. Never merely repeat the title.
6. Provider-by-Provider analysis: cover every Provider × Access Path once. Explain best fit, observed strength, observed risk, and evidence boundary.
7. Agent integration: separate observed invalid-input behavior from unmeasured identity, schema, pagination, and semantic risks.
8. Method, offline reproduction, live rerun, contribution, disclosure, correction policy, and FAQ.

Prefer concrete developer consequences over benchmark jargon. Do not restate a table row as prose unless the explanation changes a decision.
