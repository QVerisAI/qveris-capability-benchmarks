from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import DirectBinding, DirectBindingRegistry
from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)
from qveris_bench.models.enums import (
    AccessPathType,
    CellState,
    DisclosureLevel,
    FailureAttribution,
    LicenseStatus,
    RedactionStatus,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.releases.builder import build_release
from qveris_bench.suites.compiler import CompiledSuite
from qveris_bench.suites.fingerprint import canonical_json_bytes


class PublicTerminalReleaseError(ValueError):
    pass


class PublicTerminal(FrozenModel):
    binding_id: StableId
    run_key: str = Field(min_length=1)
    provider_id: StableId
    access_path_id: StableId
    transport: AccessPathType
    state: CellState
    facts: dict[str, Any]
    unmet_conditions: tuple[str, ...]
    failure_attribution: FailureAttribution | None
    raw_digest: EvidenceRef
    binding_registry_digest: EvidenceRef
    extractor_version: SemanticVersion
    suite_fingerprint: Sha256
    redaction_status: RedactionStatus
    disclosure_level: DisclosureLevel
    license_status: LicenseStatus
    latency_ms: float | None
    cost_credits: float | None
    github_run_id: str = Field(min_length=1)
    github_sha: str = Field(pattern=r"^[a-f0-9]{40}$")


@dataclass(frozen=True)
class ValidatedTerminalOutcome:
    state: CellState
    unmet_conditions: tuple[str, ...]
    failure_attribution: FailureAttribution | None


@dataclass(frozen=True)
class PublicTerminalReleaseArtifacts:
    run_plan: RunPlan
    cells: tuple[RunCell, ...]
    evidence: tuple[EvidenceBundle, ...]
    release: BenchmarkRelease
    release_bytes: bytes
    public_evidence_manifest_bytes: bytes

    def rebuild(self) -> bytes:
        return build_release(self.release, self.cells, self.evidence)

    def files(self) -> dict[str, bytes]:
        return {
            "run-plan.json": canonical_json_bytes(
                self.run_plan.model_dump(mode="json")
            ),
            "cells.json": canonical_json_bytes(
                [cell.model_dump(mode="json") for cell in self.cells]
            ),
            "evidence.json": canonical_json_bytes(
                [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in self.evidence
                ]
            ),
            "release-input.json": canonical_json_bytes(
                self.release.model_dump(mode="json", exclude_none=True)
            ),
            "release.json": self.release_bytes,
            "public-evidence-manifest.json": self.public_evidence_manifest_bytes,
        }

    def write(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in self.files().items():
            (output_dir / name).write_bytes(content)


def assemble_public_terminal_release(
    *,
    compiled: CompiledSuite,
    binding_registry: DirectBindingRegistry,
    binding_registry_digest: str,
    terminal_paths: tuple[Path, ...],
    release_id: str,
    version: str,
    limitations: tuple[str, ...],
    outcome_validator: Callable[
        [BenchmarkCase, DirectBinding, dict[str, Any]], ValidatedTerminalOutcome
    ],
    expected_github_run_id: str,
    expected_github_sha: str,
    expected_provenance: dict[str, tuple[str, str]],
    github_artifacts_manifest_bytes: bytes,
) -> PublicTerminalReleaseArtifacts:
    planned = {cell.run_key: cell for cell in compiled.run_plan.cells}
    applicable = {key: cell for key, cell in planned.items() if cell.applicable}
    bindings = {binding.binding_id: binding for binding in binding_registry.bindings}
    cases = {case.case_id: case for case in compiled.cases}
    terminals: dict[str, tuple[PublicTerminal, Path]] = {}
    for path in terminal_paths:
        try:
            terminal = PublicTerminal.model_validate_json(path.read_bytes())
        except (OSError, ValidationError, ValueError) as exc:
            raise PublicTerminalReleaseError(
                f"invalid public terminal: {path}"
            ) from exc
        if terminal.run_key in terminals:
            raise PublicTerminalReleaseError("duplicate terminal run key")
        terminals[terminal.run_key] = (terminal, path)
    if terminals.keys() != applicable.keys():
        raise PublicTerminalReleaseError(
            "terminal run keys do not match applicable cells"
        )

    cells = []
    evidence = []
    outcome_ids = []
    for run_key, planned_cell in planned.items():
        if not planned_cell.applicable:
            cells.append(planned_cell)
            continue
        terminal, path = terminals[run_key]
        binding = bindings.get(terminal.binding_id)
        if binding is None:
            raise PublicTerminalReleaseError("terminal references an unknown binding")
        if terminal.binding_registry_digest != binding_registry_digest:
            raise PublicTerminalReleaseError(
                "terminal binding registry digest mismatch"
            )
        if terminal.suite_fingerprint != compiled.fingerprint:
            raise PublicTerminalReleaseError("terminal suite fingerprint mismatch")
        if (
            terminal.provider_id != planned_cell.provider_id
            or terminal.access_path_id != planned_cell.access_path_id
            or binding.case_id != planned_cell.case_id
            or binding.provider_id != planned_cell.provider_id
            or binding.access_path_id != planned_cell.access_path_id
            or binding.transport is not terminal.transport
        ):
            raise PublicTerminalReleaseError("terminal cell identity mismatch")
        evidence_id = f"{terminal.binding_id}-round-{planned_cell.round}"
        if path.stem != evidence_id:
            raise PublicTerminalReleaseError(
                "terminal filename does not match cell identity"
            )
        expected_outcome = outcome_validator(
            cases[planned_cell.case_id], binding, terminal.facts
        )
        if (
            terminal.state is not expected_outcome.state
            or terminal.unmet_conditions != expected_outcome.unmet_conditions
            or terminal.failure_attribution is not expected_outcome.failure_attribution
        ):
            raise PublicTerminalReleaseError(
                "terminal outcome does not match CAP-owned evaluation"
            )
        if (
            terminal.github_run_id != expected_github_run_id
            or terminal.github_sha != expected_github_sha
        ):
            raise PublicTerminalReleaseError("terminal GitHub provenance mismatch")
        if expected_provenance.get(evidence_id) != (
            sha256_digest(path.read_bytes()),
            terminal.raw_digest,
        ):
            raise PublicTerminalReleaseError("terminal artifact provenance mismatch")
        cells.append(
            planned_cell.model_copy(
                update={
                    "state": terminal.state,
                    "failure_attribution": terminal.failure_attribution,
                }
            )
        )
        evidence.append(
            EvidenceBundle(
                evidence_id=evidence_id,
                run_key=run_key,
                raw_digest=terminal.raw_digest,
                public_digest=sha256_digest(path.read_bytes()),
                redaction_status=terminal.redaction_status,
                disclosure_level=terminal.disclosure_level,
                license_status=terminal.license_status,
                extractor_version=terminal.extractor_version,
                suite_fingerprint=terminal.suite_fingerprint,
                latency_ms=terminal.latency_ms,
                cost_credits=terminal.cost_credits,
            )
        )
        outcome_ids.append(f"{evidence_id}-{terminal.state.value.replace('_', '-')}")
    run_plan_bytes = canonical_json_bytes(compiled.run_plan.model_dump(mode="json"))
    public_manifest_bytes = canonical_json_bytes(
        {
            "github_run_id": expected_github_run_id,
            "github_sha": expected_github_sha,
            "github_artifacts_manifest_digest": sha256_digest(
                github_artifacts_manifest_bytes
            ),
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "run_key": item.run_key,
                    "path": f"evidence/{release_id}/{item.evidence_id}.json",
                    "public_digest": item.public_digest,
                    "raw_digest": item.raw_digest,
                }
                for item in sorted(evidence, key=lambda item: item.evidence_id)
            ],
        }
    )
    release = BenchmarkRelease(
        release_id=release_id,
        version=version,
        suite_fingerprint=compiled.fingerprint,
        run_plan_digest=sha256_digest(run_plan_bytes),
        public_evidence_manifest_digest=sha256_digest(public_manifest_bytes),
        github_artifacts_manifest_digest=sha256_digest(github_artifacts_manifest_bytes),
        evidence_ids=tuple(sorted(item.evidence_id for item in evidence)),
        outcome_ids=tuple(sorted(outcome_ids)),
        cap_id=compiled.run_plan.cap_id,
        cap_version=compiled.run_plan.cap_version,
        cap_sources=compiled.run_plan.cap_sources,
        limitations=limitations,
    )
    ordered_cells = tuple(sorted(cells, key=lambda item: item.run_key))
    ordered_evidence = tuple(sorted(evidence, key=lambda item: item.evidence_id))
    return PublicTerminalReleaseArtifacts(
        run_plan=compiled.run_plan,
        cells=ordered_cells,
        evidence=ordered_evidence,
        release=release,
        release_bytes=build_release(release, ordered_cells, ordered_evidence),
        public_evidence_manifest_bytes=public_manifest_bytes,
    )
