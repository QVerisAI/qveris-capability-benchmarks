# Government Bond Yield CAP Article Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Produce a release-backed English comparison article for Harbor `RATES.GOVT_BENCHMARK` and prove that the CAP Article Factory can repeat the Corporate Actions workflow without a second article architecture.

**Architecture:** Keep Core generic. Add one versioned Government Bond Yield CAP Pack and CAP-owned extractor, run every applicable Provider × QVeris Access Path directly, assemble immutable baseline and market Releases from GitHub-attested public/private artifacts, build one Selection Snapshot, then use the existing writer input, `cap-article-writer` Skill, Article Factory, charts, package manifest, and offline reproduction service.

**Tech Stack:** Python 3.12, Pydantic, pytest, YAML/JSON, QVeris Search/Describe/Execute, GitHub Actions artifacts, Matplotlib/Pillow, Markdown.

---

## Gap Analysis

| 功能 | 现有实现 | 缺口 | 行动 |
|---|---|---|---|
| Harbor provenance | `cap_packs/corporate-actions/v2/cap.yaml` freezes Harbor catalog and contract digests | `RATES.GOVT_BENCHMARK` has no formal local CAP Pack | Add one v1 CAP Pack with exact Harbor ID/version/digests and reject source drift |
| Candidate discovery | `.github/workflows/qveris-discovery.yml` performs credentialed Search without exposing the key | No frozen bond-yield candidate set, dispositions, or canonical bindings | Run discovery first, retain one canonical tool per Harbor Provider, freeze candidate provenance and terminal dispositions |
| Questions and matrix | Generic suite compiler and run keys already enforce Provider × Access Path × Case × Round | No seven-country 10Y cases or `ZZ` negative control | Add a root executable pack with baseline `suite.yaml`/`cases.yaml` and a seven-country market suite; stop when fewer than two applicable paths remain |
| CAP evaluation | `corporate_actions/direct.py` demonstrates CAP-owned extraction and outcome validation | Bond rows need finite value, ISO date, benchmark identity, unit/currency/source handling | Add CAP-local request identity and provider-shape extraction; do not add bond fields to Core |
| Live evidence | Corporate Actions E2E persists private execution envelopes and sanitized public terminals | No bond live-cell producer or workflows | Add baseline/market workflows and E2E using the same QVeris client and artifact stores |
| Release assembly | `assemble_public_terminal_release` is generic; Corporate Actions script verifies GitHub exports and private envelopes | Artifact export verification is embedded in a Corporate-specific script | Extract only the artifact-verification mechanics that are truly shared; keep outcome evaluation CAP-owned |
| Selection facts | `build_selection_snapshot` already consumes two Releases, list pricing, official pricing, market states, latency, and Agent observations; writer input includes digest-bound public terminal facts | No bond configuration or sanitized Inspect snapshot | Reuse the frozen publication runtime unchanged; expose semantic fields through existing profile sample labels and public observations |
| Editorial writing | `build_writer_input`, `.agents/skills/cap-article-writer`, and Article Factory separate deterministic facts from prose | No bond publication profile/editorial document | Generate editorial only from writer input and Skill; all numbers, identities, links, tables, and charts remain renderer-owned |
| Publication proof | Corporate adapter rebuilds Snapshot/writer input/article/charts and binds top-level guide | No bond package manifest, adapter entry point, or attestation | Add a thin adapter and manifest using the same reproduce contract |
| Stability measurement | No standard elapsed/manual-intervention artifact for a second CAP | Cannot prove the promised repeatability | Record timestamps, real-call count, manual edits, blockers, and final result in a concise run report |

No new database table or generic domain model is needed: all new business fields remain inside the versioned CAP Pack and its extractor; existing Release, Evidence, Selection, Article Facts, and Publication models are reused.

## Acceptance Criteria

- **AC1 — Exact Harbor source:** CAP Pack, suites, Releases, and Snapshot all identify Harbor `RATES.GOVT_BENCHMARK` contract v1 with verified catalog and contract digests.
- **AC2 — Frozen measurement:** Baseline US plus `ZZ`, and a market Release containing all seven US/CN/UK/DE/JP/AU/CA 10Y cases, run twice for every applicable Provider × QVeris Access Path; Provider and Access Path remain separate identities.
- **AC3 — Bounded live cost:** The two publishable canonical Provider paths produce exactly 36 planned Execute calls: baseline 8 and seven-country market 28. Search/Describe activity and Inspect list prices are reported separately.
- **AC4 — Trustworthy evidence:** 401/402/403/429/5xx/timeouts/network errors are infra-blocked, not provider-negative; successful facts contain a finite numeric yield, ISO date inside the fixed 2024 window, and verified country/tenor identity; private raw and account billing never enter public artifacts.
- **AC5 — Reader-value article:** English answer-first guide includes scoped recommendations, comparison table, seven-country state matrix/chart, latency × public Inspect list-price chart, per-path analysis, Agent integration notes, methods, concrete offline replay, live rerun, contribution, disclosure, corrections, and FAQ.
- **AC6 — Full reproduction:** Release replay and publication reproduction work without provider credentials and fail on contract, binding, evidence, Snapshot, article fact, chart, link, guide, or package drift.
- **AC7 — Stability evidence:** A run report states elapsed time by phase, actual Execute count, manual interventions, and whether the second CAP used the same production path.

## Impact Analysis and Invariants

- The data path is `Harbor contract → CAP Pack → compiled Run Plan → Direct binding → private execution envelope → sanitized public terminal → immutable Release → Selection Snapshot → writer input → Skill editorial → deterministic article/charts → Publication Package`.
- Authentication and transport stay in the existing QVeris client. The bond extractor receives only the captured response envelope and cannot log the API key.
- The release builder must re-evaluate public terminal outcomes from matching private response/failure-envelope bytes and frozen request identity before publishing.
- `provider_negative` is allowed only for a CAP-level failure or explicit invalid-input rejection; transport and entitlement failures remain `infra_blocked`.
- Market states remain distinct: `verified`, `provider_negative`, `not_applicable`, and `evidence_insufficient` are never collapsed.
- QVeris Inspect list credits and account-billed credits remain separate; the latter are excluded from all public files.
- The Article Factory remains the single renderer. No bond-specific Markdown generator, chart renderer, or duplicate Selection model is introduced.

## Task 1: Freeze Discovery and Formal CAP Inputs

**Files:**
- Create: `cap_packs/govt-bond-yield/cap.yaml`
- Create: `cap_packs/govt-bond-yield/observation-schema.yaml`
- Create: `cap_packs/govt-bond-yield/outcome-rules.yaml`
- Create after discovery: `cap_packs/govt-bond-yield/candidate-source-manifest.yaml`
- Create after discovery: `cap_packs/govt-bond-yield/candidate-dispositions.yaml`
- Modify: `providers/alpha-vantage/provider.yaml`
- Create: `providers/stlouisfed-fred/provider.yaml`
- Create: `providers/qveris-finance/provider.yaml`
- Modify: `question_bank/capabilities.yaml`
- Test: `tests/cap_packs/test_govt_bond_yield_acceptance.py`

- [ ] Write failing acceptance tests for exact Harbor source, exact candidate-source set/digest, dispositions, and question ownership.
- [ ] Trigger the existing QVeris discovery workflow with a narrow government-bond-yield query and download the public candidate summary.
- [ ] Select at most one canonical Direct binding per frozen Provider identity; require at least two applicable Provider × Path rows.
- [ ] Freeze the sanitized candidate manifest and all terminal dispositions, including rejection reasons.
- [ ] Freeze source Provider aliases, official source URLs, execution authorization, license clearance, and Inspect-price availability; stop with an evidence-insufficient run report if fewer than two paths pass the gate.
- [ ] Exclude Alpha Vantage because its US-only Treasury Yield tool cannot express the CAP-owned unsupported-country negative control; do not construct a substitute negative.
- [ ] Add the formal CAP contract and promote only its owned question family to runnable.
- [ ] Run `uv run pytest tests/cap_packs/test_govt_bond_yield_acceptance.py -q`.

## Task 2: Compile the Seven-Country Direct-Test Matrix

**Files:**
- Create: `cap_packs/govt-bond-yield/cases.yaml`
- Create: `cap_packs/govt-bond-yield/market-cases.yaml`
- Create: `cap_packs/govt-bond-yield/suite.yaml`
- Create: `cap_packs/govt-bond-yield/market-suite.yaml`
- Create: `cap_packs/govt-bond-yield/direct-bindings.json`
- Create: `cap_packs/govt-bond-yield/market-direct-bindings.json`
- Create: `cap_packs/govt-bond-yield/provider-bindings.yaml`
- Test: `tests/cap_packs/test_govt_bond_yield_acceptance.py`

- [ ] Write failing tests for the seven-country market Release including US, baseline US plus one negative control, two rounds, direct-only mode, and bounded applicable calls.
- [ ] Freeze country/tenor request parameters from Search/Describe results; mark only contract-backed non-applicability.
- [ ] Validate every binding against the compiled suite, provider registry, and CAP source.
- [ ] Assert baseline calls =8, market calls =28, and total Execute calls =36.
- [ ] Run the CAP acceptance test.

## Task 3: Add CAP-Owned Extraction and Outcome Rules

**Files:**
- Create: `src/qveris_bench/cap_packs/govt_bond_yield/__init__.py`
- Create: `src/qveris_bench/cap_packs/govt_bond_yield/models.py`
- Create: `src/qveris_bench/cap_packs/govt_bond_yield/direct.py`
- Test: `tests/cap_packs/test_govt_bond_yield_direct.py`

- [ ] Write provider-shape tests for finite numeric yield including zero/negative values, latest ISO date inside the fixed 2024 window, requested country/tenor, optional unit/currency/source, wrong benchmark identity, NaN/infinity, empty data, explicit invalid-input rejection, and transport failures.
- [ ] Implement exact frozen request-identity validation; provider aliases must be explicit and venue/country semantics cannot be erased.
- [ ] Implement response extraction per selected binding, returning only sanitized terminal facts.
- [ ] Implement offline `validate_public_outcome` so Release assembly and replay enforce the same CAP contract.
- [ ] Run direct evaluator tests and the CAP acceptance test.

## Task 4: Produce Attested Live Evidence

**Files:**
- Create: `tests/e2e/test_live_govt_bond_yield.py`
- Create: `.github/workflows/live-govt-bond-yield-baseline-e2e.yml`
- Create: `.github/workflows/live-govt-bond-yield-market-e2e.yml`
- Modify only if shared extraction is clean: `src/qveris_bench/releases/github_artifacts.py`
- Modify only if shared extraction is clean: `scripts/build_corporate_actions_v2_release.py`
- Create: `scripts/build_govt_bond_yield_release.py`
- Modify: `src/qveris_bench/execution/qveris.py`
- Modify: `src/qveris_bench/execution/http.py`
- Test: `tests/scripts/test_build_govt_bond_yield_release.py`

- [ ] Write failing tests that bind GitHub run, artifact ID/archive digest, cell identity, tool ID, request-parameter digest, private response digest, public terminal digest, and CAP-owned outcome.
- [ ] Reuse the existing live QVeris execution client, private execution envelope, raw store, and sanitized public terminal shape; add a versioned private failure envelope for timeout, network, non-JSON, missing-result, and protocol-shape failures so every applicable matrix cell terminates.
- [ ] Keep account `cost_credits` private and exclude it before the public artifact upload, not only during Release assembly.
- [ ] Extract shared GitHub ZIP/export verification only if it reduces duplication without changing Corporate outcome behavior.
- [ ] Open/update the PR as soon as this minimal end-to-end slice is reviewable, then let CI run while live workflows proceed.
- [ ] Run baseline and market workflows using the repository secret. Total Execute calls must not exceed the compiled bound.
- [ ] Download exact GitHub exports/artifacts, assemble new immutable Release IDs, replay them offline, and commit only sanitized public evidence and Release files.

## Task 5: Build the Selection Snapshot

**Files:**
- Create: `selection_snapshots/govt-bond-yield-v1/selection-snapshot.yaml`
- Create: `selection_snapshots/govt-bond-yield-v1/qveris-list-pricing.json`
- Create: `selection_snapshots/govt-bond-yield-v1/selection-snapshot.json`
- Optional only with official evidence: `selection_snapshots/govt-bond-yield-v1/official-pricing-supplement.json`
- Test: `tests/profiles/test_govt_bond_yield_selection.py`

- [ ] Write failing tests for exact Release digests, Provider × Path separation, seven market states, latency samples, Inspect list prices, no account-cost facts, and explicit evidence insufficiency.
- [ ] Keep the historical Corporate publication runtime source files byte-for-byte unchanged because its external attestation binds them.
- [ ] Project benchmark identity, date, unit, currency, and source through the existing digest-bound writer public observations and profile sample labels.
- [ ] Capture sanitized `qveris inspect` list credits for the frozen tools and bind the snapshot digest/date.
- [ ] Build the Snapshot from the two Releases; do not hand-edit generated JSON.
- [ ] Keep official Provider pricing evidence-insufficient unless an official URL, date, scope, and digest are frozen.
- [ ] Rebuild and byte-compare the committed Snapshot in tests.

## Task 6: Generate Skill-Constrained Editorial and Article Package

**Files:**
- Create: `docs/guides/capability-seo/best-government-bond-yield-apis/publication-profile.yaml`
- Create: `docs/guides/capability-seo/best-government-bond-yield-apis/writer-input.json`
- Create: `docs/guides/capability-seo/best-government-bond-yield-apis/editorial.json`
- Generate: `docs/guides/capability-seo/best-government-bond-yield-apis/article-facts.json`
- Generate: `docs/guides/capability-seo/best-government-bond-yield-apis/article.md`
- Generate: `docs/guides/capability-seo/best-government-bond-yield-apis/charts/*`
- Generate: `docs/guides/capability-seo/best-government-bond-yield-apis/manifest.json`
- Create: `docs/guides/best-government-bond-yield-apis.md`
- Test: `tests/articles/test_govt_bond_yield_writer.py`
- Test: `tests/articles/test_govt_bond_yield_factory.py`

- [ ] Write failing tests for the fixed article sections, seven-country chart, comparison chart, all path analyses, concrete rerun/reproduce commands, approved links, and English-only reader-facing copy.
- [ ] Build writer input solely from Snapshot plus replayed public evidence.
- [ ] Use `.agents/skills/cap-article-writer/SKILL.md` to produce editorial JSON with fact references; never give the model private raw evidence or ownership of material values/links.
- [ ] Build the deterministic article package and project it to the top-level guide.
- [ ] Compare it section-by-section with the Dividend and Corporate Actions golden articles; revise the Skill only for a reusable editorial failure, then rebuild.

## Task 7: Bind and Reproduce the Publication

**Files:**
- Create: `src/qveris_bench/cap_packs/govt_bond_yield/publication.py`
- Modify: `pyproject.toml`
- Create: `docs/guides/capability-seo/best-government-bond-yield-apis/manifest.yaml`
- Create: `docs/guides/publication-attestations/best-government-bond-yield-apis-2026-08-14-v1.json`
- Test: `tests/publications/test_govt_bond_yield_publication.py`

- [ ] Write failing mutation tests for wrong Release refs, stale Snapshot, unbound evidence, changed editorial, chart pixel/alpha drift, unapproved link, guide drift, adapter source drift, and expected package digest mismatch.
- [ ] Add a thin publication adapter that rebuilds Snapshot, writer input, article facts, charts, links, and top-level projection.
- [ ] Bind every executed adapter/helper source and both Release digests in the Publication manifest.
- [ ] Add an external package attestation and render a shell-valid concrete offline reproduction command.
- [ ] Publish the expected package digest through a protected GitHub workflow output or Release asset and bind the in-repo attestation to that external anchor.
- [ ] Run Release replay and publication reproduction without `QVERIS_API_KEY`.

## Task 8: Validate Stability, Review Once, and Merge

**Files:**
- Create: `docs/audits/2026-08-14-govt-bond-yield-article-run.md`
- Remove before final PR if process-only: `docs/superpowers/plans/2026-08-14-govt-bond-yield-cap-article.md`

- [ ] Record phase timestamps, discovery count, selected paths, actual Execute count, API/CI blockers, manual editorial interventions, generated artifacts, and replay digests.
- [ ] Run changed-area pytest, live-result acceptance, Ruff, and mypy; let PR CI own the full suite.
- [ ] Commit small reviewable units, push the branch, and ensure the PR is current with `master`.
- [ ] Run exactly one PR review phase with two parallel reviewers: code reviewer and silent-failure hunter.
- [ ] Triage all findings together; fix every P0/P1 and valid P2 in one batch, push once, then perform at most one re-review.
- [ ] Run `postmortem-learning` for reusable failures or user corrections and place learnings in tests/Skill/project docs as appropriate.
- [ ] Merge only when CI and required review are green, then clean the dedicated worktree.

## Verification Commands

- `uv run pytest tests/cap_packs/test_govt_bond_yield_acceptance.py tests/cap_packs/test_govt_bond_yield_direct.py -q`
- `uv run pytest tests/e2e/test_live_govt_bond_yield.py tests/scripts/test_build_govt_bond_yield_release.py -q`
- `uv run pytest tests/profiles/test_govt_bond_yield_selection.py tests/articles/test_govt_bond_yield_writer.py tests/articles/test_govt_bond_yield_factory.py tests/publications/test_govt_bond_yield_publication.py -q`
- `uv run ruff check src tests scripts`
- `uv run mypy src`
- `uv run qveris-bench release replay releases/<baseline-release-id> --expected-digest <baseline-digest>`
- `uv run qveris-bench release replay releases/<market-release-id> --expected-digest <market-digest>`
- `uv run qveris-bench publication reproduce --package docs/guides/capability-seo/best-government-bond-yield-apis/manifest.yaml --expected-package-digest <published-package-digest>`
