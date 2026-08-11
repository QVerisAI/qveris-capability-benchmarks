# Contributing

Thank you for helping financial Agent developers make evidence-based Provider and
Access Path decisions. Benchmark independence and official-result rules are defined
in [GOVERNANCE.md](GOVERNANCE.md).

## Choose a contribution path

- **Provider submission:** propose an official Access Path with the
  [Provider submission form](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=provider-submission.yml).
  Follow `docs/adding-a-provider.md`; never include a credential or private response.
- **CAP and method contribution:** propose a developer decision, cases, ground truth,
  or outcome rules with the
  [CAP and method form](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=cap-method-proposal.yml).
- **Result challenge:** identify a released fact and counter-evidence with the
  [Result challenge form](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=result-challenge.yml).
- **Code or documentation:** open a focused pull request after reading the
  architecture and local checks below.

An early idea can start as an Issue. A change to executable cases, rules, extractors,
adapters, evidence policy, or release behavior requires a pull request and tests.

## Before opening a change

1. Read `AGENTS.md`, `docs/architecture/platform.md`, and
   `docs/architecture/repository-map.md`.
2. Keep Core generic; put capability semantics in a CAP Pack and transport behavior
   in an Access Path adapter.
3. Define measurable acceptance criteria and write a failing test before production
   behavior.
4. Record question provenance, redistribution terms, and conflicts of interest.
5. Do not include credentials, private raw responses, local run state, personal data,
   or material whose redistribution terms are unknown.

Provider and Access Path identities must remain separate. A contribution must not
add aggregate scores, global winners, or an Agent-friendly rating.

## Local checks

Use Python 3.12 and the locked environment.

```bash
uv sync --locked --all-groups
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run qveris-bench schema export --check
```

When release files change, also replay the affected directory:

```bash
uv run qveris-bench release replay releases/<release-id>
```

## Pull requests

Keep commits small and reviewable. The pull request must state:

- scope and acceptance criteria;
- affected CAP, Provider, and Access Path identities;
- tests and real execution evidence;
- disclosure, licensing, redaction, and conflict considerations;
- known limitations and compatibility impact.

The contributor must have the right to submit the change. Code is contributed under
Apache-2.0. Newly authored cases and documentation are contributed under CC BY 4.0
unless the artifact explicitly identifies another compatible license.
