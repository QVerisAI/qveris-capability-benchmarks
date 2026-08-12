# AI Evolution Board Log

## 2026-08-12 — Dimension metric policy

- **Rule:** Ban composite conclusions, not useful vocabulary or evidence-bound
  measurements. A dimension score must identify its CAP, Provider, Access Path,
  versioned method, suite, and evidence; a ranking must additionally publish a
  complete frozen cohort.
- **Why:** Rejecting every `score`, `rating`, or `agent_friendly` key erased useful
  per-dimension comparisons while providing only superficial protection against
  opaque composites.
- **How to apply:** Put permitted measurements in typed metric fields, reject ad-hoc
  metric keys in free-form details, and validate cohort completeness plus evidence
  ownership at the release gate. Keep Provider totals, Agent-friendly composites,
  and cross-CAP or cross-task rankings prohibited.
