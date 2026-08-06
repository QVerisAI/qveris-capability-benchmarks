# QVeris Capability Benchmarks

QVeris Capability Benchmarks is an open, evidence-first platform for comparing
provider capabilities in concrete AI Agent tasks. It is designed to answer a
practical question: for a specific capability and access path, can a provider's
official machine interface complete the developer's task under disclosed test
conditions?

This repository is in early development. The first implementation milestone
establishes the repository contract and architecture; benchmark execution and
public releases arrive in later reviewed milestones.

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

## Planned workflow

```text
CAP source -> frozen suite -> run plan -> private raw evidence
           -> sanitized observations -> task outcomes -> release bundle
```

Stages 1–4 build and run benchmarks. Later publication and provider-feedback
systems consume immutable release facts; they are not implemented here.

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
