# Contributing

Thank you for helping make provider selection more evidence-based.

## Before opening a change

1. Read `AGENTS.md` and `docs/architecture/platform.md`.
2. Keep Core generic; put capability semantics in a CAP Pack and transport behavior
   in an Access Path adapter.
3. Define measurable acceptance criteria and write a failing test before production
   behavior.
4. Do not include credentials, private raw responses, local run state, or material
   whose redistribution terms are unknown.

## Local checks

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Pull requests should explain the capability or platform contract being changed,
the evidence and test coverage, disclosure or licensing considerations, and any
known limitations. Contributions must be compatible with Apache-2.0 for code and
CC BY 4.0 for newly authored cases or documentation unless explicitly identified.
