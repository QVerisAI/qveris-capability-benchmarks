# Open Benchmark Ecosystem

The project turns single-CAP measurements into evidence that financial Agent
developers can inspect, challenge, and eventually rerun through their own Access
Paths. Articles distribute conclusions; the repository is the source of truth that
proves how those conclusions were produced.

```text
single-CAP release -> evidence-linked article -> developer replay or challenge
                   -> better cases and methods -> more Provider participation
                   -> broader neutral evidence -> more developer adoption
```

The flywheel depends on trust, not traffic alone. An article claim must preserve its
CAP, release ID, Access Path, as-of context, and evidence anchor. Commercial access
may make execution easier; it cannot buy benchmark treatment.

## Developer

A developer starts from one product decision and one CAP. They can inspect a release
or run the [offline replay](../release-replay.md) without credentials. If a fact is
wrong, stale, or unsupported, they use the Result challenge form linked from
`CONTRIBUTING.md`.

## Provider

A Provider identifies an official Native or QVeris Access Path and follows the
[provider guide](../adding-a-provider.md). Self-tests enter as submitted evidence.
Only a maintainer rerun can produce an official project result; an independent live
run may later add community reproduction evidence.

## Contributor

A contributor can propose source-backed cases, outcome rules, CAP Packs, adapters,
tests, or documentation through [CONTRIBUTING.md](../../CONTRIBUTING.md). New methods
must preserve the single-CAP boundary, licensing provenance, failure attribution,
and the prohibition on provider-total and cross-CAP composite rankings. Versioned,
evidence-bound per-dimension rankings within one frozen cohort are permitted.

## Trust layers

| Layer | Operation | Trust established |
|---|---|---|
| Offline release replay | Rebuild committed release bytes without network access | The checked-out directory is internally consistent |
| Authenticity verification | Compare with a digest from a trusted external anchor | The bundle matches that published identity |
| Maintainer rerun | Execute the frozen suite through an Access Path | The official operator observed a new live result |
| Community reproduction | Independent live execution with disclosed environment | A third party observed a comparable result |

The layers are cumulative but never interchangeable. Later verification is appended
as an attestation or successor release; immutable release bytes are not edited.

## Architecture boundary

Core continues to own generic suite, execution, evidence, and release contracts.
CAP Packs own domain semantics. Adapters own authentication, transport, raw response
persistence, and Provider error normalization. Articles, sites, and Task Fit
Profiles consume released facts and do not become alternate benchmark engines.

No new database is needed for the current phase. Existing `BenchmarkRelease`,
`RunPlan`, `RunCell`, and `EvidenceBundle` records contain the facts required for
offline replay. Evolving challenge and reproduction states require a future
append-only attestation or release-status design because they cannot be derived from
existing immutable fields.

## Roadmap

| Phase | Capability | Status |
|---|---|---|
| Trust core | Offline release replay, governance, structured contribution intake | v1 implementation |
| Golden CAP | Three or more Providers and at least one paired Native / QVeris comparison | next evidence milestone |
| Local live rerun | QVeris Key and at least one Native BYOK path with new evidence | not implemented in v1 |
| Managed consumers | Hosted BYOK, scheduled runs, independent site, Provider Portal, database | not implemented in v1 |

The project validates the manual submission, challenge, and supersession loop before
building managed workflow software.

## Success measures

- time for a new developer to complete their first offline replay;
- percentage of material article claims linked to release facts and evidence;
- independent live reproductions per released CAP;
- time from a supported challenge to a public disposition;
- accepted external cases or methods that improve a released CAP.

Stars are useful distribution evidence, but they are not a substitute for replay,
challenge, contribution, or adoption.
