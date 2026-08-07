# QVeris Capability Benchmarks

QVeris Capability Benchmarks is an open, evidence-first platform for comparing
provider capabilities in concrete AI Agent tasks. It is designed to answer a
practical question: for a specific capability and access path, can a provider's
official machine interface complete the developer's task under disclosed test
conditions?

The v1 Core, CAP contracts, Direct-Test execution path, evidence pipeline, and
immutable release flow are implemented. The repository currently contains the
ETF Holdings benchmark release and a deliberately narrow Stock Quote smoke CAP.
It is not a provider leaderboard and does not publish a composite score.

## Principles

- Direct Tests are required for every included provider and access path.
- Agent Trials expose exactly one preselected canonical tool.
- Native and QVeris access paths are run and disclosed separately.
- Results are factual observations and categorical task outcomes, not a provider
  total score or an Agent-friendly composite rating.
- Public facts remain traceable to sanitized evidence and private raw digests.
- Git-backed, versioned files are the v1 source of truth; v1 has no database.

The platform is greenfield. `qveris-agent-harness` may be cited as provenance for
source questions, but it is not a code, schema, or runtime dependency.

## Workflow

```text
CAP source -> frozen suite -> run plan -> private raw evidence
           -> sanitized observations -> task outcomes -> release bundle
```

Stages 1–4 build and run benchmarks, including immutable release bundles. The
stage 5 and 6 consumer systems—such as a leaderboard website and provider-feedback
operations—are not implemented here.

## Code reading map

Start with [the repository map](docs/architecture/repository-map.md). It follows
one benchmark from CAP configuration through suite compilation, execution,
evidence, outcome evaluation, and release generation. The map also distinguishes
generic Core code from CAP-owned domain logic.

## Development

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run mypy src
uv run qveris-bench --help
```

See [the platform architecture](docs/architecture/platform.md),
[contribution guide](CONTRIBUTING.md), and [data license](DATA_LICENSE.md).

## Licenses

Platform code is licensed under Apache-2.0. QVeris-authored benchmark cases and
documentation are licensed under CC BY 4.0 unless an artifact says otherwise.
Third-party sources retain their original licenses and attribution requirements.
