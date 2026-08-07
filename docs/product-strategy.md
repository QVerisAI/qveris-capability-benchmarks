# Product Strategy: Financial Agent Provider Selection

**Status:** Approved direction
**Date:** 2026-08-07

## Product objective

QVeris Capability Benchmarks helps financial Agent developers choose the provider
and Access Path that fit a concrete product task. It answers a buying and engineering
decision, not the abstract question of which provider is globally best.

The product starts from the developer's intended workflow: market monitoring,
company research, filing evidence, ETF analysis, financial news, or macro research.
It then exposes the atomic evidence needed to decide which interfaces can support
that workflow, under what conditions, and with how much integration risk.

## Product unit and measurement unit

**Financial Task is the product unit. CAP is the measurement unit.**

A Financial Task reflects the developer's language and product intent. A CAP is one
bounded machine-interface capability that can be tested, attributed, and replayed
without mixing provider behavior with model planning or unrelated tools.

```text
Financial Task -> required CAPs -> provider and Access Path cells
               -> Direct Test and constrained Agent Trial evidence
               -> task-fit profile for the developer
```

The public experience should lead with Financial Tasks. CAPs remain the stable
evaluation substrate and evidence drill-down. A task may compose several CAPs, but
an individual benchmark case stays atomic.

This direction does not add a Financial Task runtime model, database, or leaderboard
site to v1. It defines how later consumers organize the release facts already
produced by the CAP platform.

## Primary differentiation: Agent-interface fitness

Traditional financial benchmarks test model knowledge or answer correctness. API
directories list endpoints. Provider pages describe claimed coverage. QVeris tests
the missing layer: whether an official financial machine interface is practical for
an Agent developer to integrate and operate.

Agent-interface fitness is a first-class set of observations:

- **single-tool task closure:** whether the atomic task can be completed through
  the one suite-frozen canonical tool;
- **parameter contract:** whether required inputs, enums, dates, markets, units, and
  defaults are explicit enough for reliable parameter construction;
- **response schema:** whether types, identifiers, timestamps, units, currencies,
  provenance, and empty states are stable and machine-consumable;
- **error recoverability:** whether invalid input, entitlement, rate limit, timeout,
  and no-data states tell an Agent whether to correct, retry, ask, or stop;
- **pagination and truncation:** whether continuation, completeness, limits, and
  Top N behavior prevent silent partial answers;
- **language mapping:** whether natural-language financial requests map reliably to
  canonical symbols, markets, dates, and interface vocabulary;
- **operational effort:** observed calls, corrections, retries, tokens, and elapsed
  time required to reach a categorical outcome.

There is no Agent-friendly composite score. Each observation remains visible so a
developer can apply the priorities of their own product. Discovery, routing,
multi-tool planning, and tool-selection metrics remain outside the benchmark; an
Agent Trial receives one predetermined canonical tool.

## Developer selection dimensions

Every task-fit profile should disclose the dimensions that materially change a
developer's choice:

| Dimension | Decision evidence |
|---|---|
| Task completion | Required facts, negative controls, categorical outcome |
| Data quality | accuracy, precision, units, freshness, provenance, citations |
| Performance | latency distributions, timeout behavior, reliability across rounds |
| Economics | cost per successful task, pricing basis, plan or entitlement limits |
| Geographic fit | country and market coverage, exchanges, instruments, calendars |
| Language fit | language coverage for requests, content, metadata, and errors |
| Agent integration | Agent interface observations defined above |
| Access constraints | authentication, quota, licensing, environment, path type |

Accuracy and precision require a CAP-owned reference or rule; marketing claims do
not become measured facts. Latency, reliability, and cost retain their disclosed
environment and plan. Declared country, market, or language coverage is distinct
from coverage demonstrated by executable cases.

## Evidence model

Direct Test establishes provider-interface facts: returned data, completeness,
precision, coverage, freshness, pagination, errors, latency, and stability. It is
mandatory for every included applicable provider cell.

The constrained Agent Trial observes whether a fixed Agent can use one predetermined
canonical tool to construct parameters, recover from interface feedback, interpret
the response, and complete the same atomic task. It cannot replace Direct Test, and
its failures must distinguish interface behavior from Agent output behavior.

Native and QVeris Access Paths remain separate. A QVeris result never stands in for
the provider's native interface, and commercial participation never changes an
observed outcome.

## Decision output

The product publishes task-fit profiles, not a universal ranking. A useful conclusion
explains that one path may fit a low-latency US market monitor, another may fit a
cross-market research Agent, and another may require an adapter because its errors
or pagination are ambiguous.

There is no context-free best provider, provider total score, or cross-task composite.
The developer sees the evidence, limitations, and integration tradeoffs behind each
task-specific conclusion.

## Initial reference task

The first reference composition is a **Company Research Agent** because it exercises
the strongest differentiator across several independent CAPs:

- Stock Quote;
- Historical Price Series;
- Company Fundamentals;
- Financial Statement Facts;
- SEC Filing Evidence;
- Financial News Evidence.

The reference task is a product-facing composition target, not permission to turn
these CAPs into one opaque end-to-end score. Each CAP must still be qualified,
executed, evidenced, and released independently before its facts can support the
task-fit profile.

## Strategic test

Every future feature or publication should answer three questions:

1. Which financial Agent developer decision does this help make?
2. Which atomic CAP evidence supports the conclusion?
3. Does the output preserve observable tradeoffs instead of hiding them in a score?

If any answer is missing, the work does not advance the product objective.
