# QVeris Capability Benchmarks

Open, evidence-first benchmarks for financial Agent developers. Choose a provider and Access Path
for one concrete capability from replayable evidence.

Every official benchmark release evaluates exactly one CAP. Native APIs, native MCP
interfaces, and QVeris Access Paths remain separate test cells, run under the same
frozen cases and outcome rules. The project publishes observable facts,
evidence-bound per-dimension metrics, and limitations—not a provider total score or
an Agent-friendly composite.

## Verify a published release

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```bash
git clone https://github.com/QVerisAI/qveris-capability-benchmarks.git
cd qveris-capability-benchmarks
uv sync --locked --all-groups
uv run qveris-bench release replay releases/<published-harbor-cap-release>
```

The first formal release will be published only after its CAP Pack is bound to a
real Harbor contract export. This offline replay validates the frozen run plan, terminal cells, public
evidence, and canonical release bytes without credentials or provider calls. It
proves that the checked-out inputs deterministically rebuild the published bundle;
it is not a live rerun. See the [release replay guide](docs/release-replay.md) for
the full trust boundary and optional external digest verification.

## What the project measures

- Direct Test outcomes for every included applicable Provider / Access Path cell.
- Separate observations for parameter clarity, response schema, error recovery,
  pagination, language mapping, and single-tool task completion.
- Evidence lineage and limitations for every public fact, plus failure attribution
  when recorded. New official releases require Provider-side attribution for every
  Provider-negative outcome; named historical bundles retain their original bytes.
- Native and QVeris paths independently, even when one path performs worse.
- Per-dimension scores and rankings only when an independently supplied CAP registry,
  content-addressed method, released evidence, and one digest-verified frozen
  Provider / Access Path cohort define the comparison.

Accuracy, precision, latency, reliability, cost, market coverage, language
coverage, and Agent interface behavior are the target task-fit profile dimensions.
A dimension remains unavailable or evidence-insufficient until a CAP defines its
measurement and a release carries supporting evidence.

## Participate

| You are | Start here | What happens next |
|---|---|---|
| Developer | [Replay a release](docs/release-replay.md) | Verify published artifacts, inspect evidence, or challenge a result |
| Provider | [Add a provider](docs/adding-a-provider.md) | Submit an Access Path for maintainer qualification and rerun |
| Contributor | [Contribution guide](CONTRIBUTING.md) | Propose CAP cases, methods, adapters, tests, or documentation |

Benchmark independence, conflicts of interest, corrections, and verification states
are governed by [GOVERNANCE.md](GOVERNANCE.md). Never put API keys or private raw
responses in an issue or pull request.

## Architecture principles

- A CAP is the atomic benchmark and release boundary.
- Future Financial Tasks may consume facts from independent CAP releases; they
  never merge CAP execution, attribution, or outcomes.
- Direct Tests are mandatory. An Agent Trial receives exactly one predetermined
  canonical tool and never replaces Direct evidence.
- Provider and Access Path identities never merge.
- Public facts retain evidence digests, extractor versions, suite fingerprints,
  disclosure status, and source-license status.
- Git-backed versioned files are the v1 source of truth; v1 has no database.

Read the [product strategy](docs/product-strategy.md), the
[repository map](docs/architecture/repository-map.md), and the
[platform architecture](docs/architecture/platform.md) before changing benchmark
contracts. The [open ecosystem architecture](docs/architecture/open-benchmark-ecosystem.md)
explains the participant journeys and phased roadmap.

## Development

```bash
uv sync --locked --all-groups
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run qveris-bench schema export --check
```

The Core is greenfield and generic. CAP semantics belong in versioned CAP Packs;
authentication and transport belong in Access Path adapters. The project does not
import runtime code from Harbor or `qveris-agent-harness`.

## Current scope

The repository implements CAP contracts, suite compilation, Direct-Test execution,
evidence gates, immutable releases, and offline release replay. Local live reruns
with a QVeris Key or Native BYOK, hosted execution, a leaderboard site, Provider
Portal, scheduler, and database are not implemented in v1.

## Licenses

Platform code is licensed under Apache-2.0. QVeris-authored benchmark cases and
documentation are licensed under CC BY 4.0 unless an artifact says otherwise.
Third-party sources retain their original licenses and attribution requirements.
See [DATA_LICENSE.md](DATA_LICENSE.md) for dataset terms.
