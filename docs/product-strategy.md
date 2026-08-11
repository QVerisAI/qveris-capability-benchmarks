# Product Strategy: Single-CAP Provider Selection

**Status:** Approved direction
**Updated:** 2026-08-11

## Product objective

QVeris Capability Benchmarks helps financial Agent developers choose the Provider
and Access Path that fit one concrete machine-interface capability. It answers a
buying and engineering decision, not the abstract question of which Provider is
globally best.

The current public benchmark and publication boundary is one CAP. A release exposes
the atomic evidence needed to decide which interfaces support that capability, under
what conditions, and with how much integration risk.

## Release and consumer boundaries

**Each benchmark release belongs to exactly one CAP. CAP is the measurement unit.**

A CAP is one bounded machine-interface capability that can be tested, attributed,
and replayed without mixing Provider behavior with model planning or unrelated
tools. Every case, Provider / Access Path cell, evidence bundle, outcome, and release
fact remains attributable to that CAP.

```text
CAP -> Provider and Access Path cells -> Direct Test evidence
    -> constrained Agent Trial observations -> immutable release facts
```

Financial Tasks and Task Fit Profiles may consume facts from multiple independent CAP releases
as a future consumer layer. They cannot merge CAP execution, attribution, evidence,
or outcomes, and they do not change the current single-CAP publication focus.

Existing `DeveloperScenario` and profile artifacts remain deterministic consumers of
pinned release facts. This direction does not expand Financial Task runtime models,
add a database, or build a leaderboard site in v1.

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

The following table is the target selection schema. It defines the dimensions that
materially change a developer's choice; it does not claim that every dimension is
implemented or published by v1.

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

v1 currently provides atomic task outcomes, access-path identity, evidence lineage,
and execution observations such as parameters, errors, retries, tokens, and elapsed
time when the applicable mode records them. It does not yet standardize cross-CAP
accuracy references, precision thresholds, latency/reliability distributions, task
cost, comprehensive geographic coverage, or a language test matrix.

Any dimension without a CAP-owned definition, repeatable measurement, and released
evidence must remain unavailable or evidence-insufficient. Declared provider metadata
or marketing claims may be disclosed as such, but cannot become measured facts.

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

The current product publishes CAP-level facts and contextual conclusions, not a
universal ranking. A useful conclusion explains that one path may fit low-latency US
quotes, another may fit cross-market coverage, and another may require an adapter
because its errors or pagination are ambiguous.

There is no context-free best provider, provider total score, or cross-task composite.
The developer sees the evidence, limitations, and integration tradeoffs behind each
task-specific conclusion.

## Future task consumer

The existing **Company Research Agent** reference composition illustrates how a
future consumer can pin facts from several independent CAP releases:

- Stock Quote;
- Historical Price Series;
- Company Fundamentals;
- Financial Statement Facts;
- SEC Filing Evidence;
- Financial News Evidence.

The reference task is not the current benchmark publication unit and is not
permission to turn these CAPs into one opaque end-to-end score. Each CAP must still
be qualified, executed, evidenced, and released independently before its facts can
support a task-fit profile.

## Strategic test

Every future feature or publication should answer three questions:

1. Which financial Agent developer decision does this help make?
2. Which atomic CAP evidence supports the conclusion?
3. Does the output preserve observable tradeoffs instead of hiding them in a score?

If any answer is missing, the work does not advance the product objective.
