# Repository Instructions

These rules apply to every change in this repository.

## Architecture boundaries

- This is a greenfield platform. Do not import from or add runtime dependencies on
  `qveris-agent-harness` or Harbor. External questions may be cited only through
  explicit source provenance.
- Keep Core generic. CAP-specific fields such as ETF holdings, ticker, quote, or
  news semantics belong in versioned CAP Packs, never in Core models or services.
- Treat Provider and Access Path as separate identities. Native and QVeris Access
  Path results must have distinct run keys and must never be merged.
- Direct Test is mandatory for every included applicable provider cell.
- A constrained Agent Trial receives exactly one single canonical tool. Do not add
  discovery, routing, multi-tool planning, or tool-selection metrics.
- Do not add an aggregate score, provider total score, Agent-friendly rating, or
  any other cross-task composite ranking.
- Adapters handle authentication, transport, raw response persistence, and provider
  error normalization. Business outcomes belong to CAP-owned extractors and rules.
- Stages 5 and 6 consume release facts only. Do not implement SEO/CMS, a leaderboard
  site, CRM, supplier portals, external BYOK, schedulers, or a database in v1.

## Evidence and security

- Inject credentials through environment variables or an approved credential
  provider. Never put credential values in configuration, traces, tests, or logs.
- Raw evidence is private by default and must live outside the public repository.
  Commit only explicitly authorized, sanitized public evidence.
- Every public fact must retain its evidence digest, extractor version, suite
  fingerprint, disclosure status, and source-license status.
- Never commit `.env`, private keys, local run directories, private/raw artifacts,
  secrets, or personally identifiable information.

## Development workflow

- Define acceptance criteria before implementation and use test-first development
  for behavior changes.
- Keep one production path; do not introduce legacy or shadow implementations.
- Run the changed-area tests, Ruff, and mypy before committing.
- Use small reviewable commits and preserve the distinction between observed facts,
  categorical task outcomes, and editorial interpretation.
- Comments are exceptional. If a non-obvious constraint needs a comment, explain
  only why it exists in one concise line.
