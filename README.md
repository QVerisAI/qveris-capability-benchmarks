# QVeris Capability Benchmarks

QVeris Capability Benchmarks is open, evidence-first selection infrastructure for
financial Agent developers. It helps a developer choose the provider and Access Path
that fit a concrete financial product task, then drill down to replayable evidence
for each atomic capability.

Financial Tasks are the product-facing unit and are stored as versioned
`DeveloperScenario` records; CAPs are the measurement unit. The
target task-fit profile is designed to compare accuracy, precision, latency,
reliability, cost, country and market coverage, language coverage, and
Agent-interface fitness without losing attribution. A dimension appears only after
its CAP defines the measurement and a release carries supporting evidence; the list
is a product target, not a claim that v1 already publishes every dimension.

The v1 Core, CAP contracts, Direct-Test execution path, evidence pipeline, and
immutable release flow are implemented. The repository currently contains the
ETF Holdings benchmark release and a deliberately narrow Stock Quote smoke CAP.
It is not a provider leaderboard and does not publish a composite score.

The primary differentiation is Agent-interface fitness: whether one predetermined
canonical tool has a clear parameter contract, stable response schema, recoverable
errors, safe pagination, sufficient context, and reliable language mapping. These
remain separate observations rather than an Agent-friendly rating.

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
Financial Task -> required CAPs -> frozen suites -> run plans
               -> private raw evidence -> sanitized observations
               -> categorical outcomes -> release facts -> task-fit profile
```

Stages 1–4 build and run benchmarks, including immutable release bundles. The
stage 5 and 6 consumer systems—such as a leaderboard website and provider-feedback
operations—are not implemented here.

## Code reading map

Start with [the repository map](docs/architecture/repository-map.md). It follows
one benchmark from CAP configuration through suite compilation, execution,
evidence, outcome evaluation, and release generation. The map also distinguishes
generic Core code from CAP-owned domain logic.

Read the [product strategy](docs/product-strategy.md) for the developer decision,
Financial Task/CAP relationship, Agent-interface criteria, and selection dimensions
that govern future work.

Future CAPs enter through the reviewed [CAP question bank](docs/question-bank.md).
It distinguishes source-backed candidate questions from runnable CAP Packs, so a
research idea cannot be mistaken for an executable benchmark.

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
