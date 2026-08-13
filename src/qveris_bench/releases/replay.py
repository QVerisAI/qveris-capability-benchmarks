from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from qveris_bench.catalog.harbor_snapshot import (
    HarborSnapshotError,
    validate_harbor_source,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.enums import CellState
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.metric import MetricDefinition
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.gate import ReleaseGateError
from qveris_bench.suites.matrix import canonical_run_key

_REQUIRED_FILES = (
    "release-input.json",
    "run-plan.json",
    "cells.json",
    "evidence.json",
    "release.json",
)
_PUBLIC_EVIDENCE_MANIFEST = "public-evidence-manifest.json"
_CELLS_ADAPTER = TypeAdapter(tuple[RunCell, ...])
_EVIDENCE_ADAPTER = TypeAdapter(tuple[EvidenceBundle, ...])
_METRIC_REGISTRY_ADAPTER = TypeAdapter(tuple[MetricDefinition, ...])
_EXECUTION_FIELDS = {"state", "failure_attribution"}


class ReleaseReplayError(ValueError):
    pass


@dataclass(frozen=True)
class ReplayResult:
    release_id: str
    published_digest: str
    expected_digest_verified: bool


def replay_release_dir(
    release_dir: Path,
    *,
    expected_digest: str | None = None,
    harbor_contracts_path: Path | None = None,
) -> ReplayResult:
    files = {name: _read_required_file(release_dir, name) for name in _REQUIRED_FILES}
    release = _validate_model(
        BenchmarkRelease,
        files["release-input.json"],
        "release-input.json",
    )
    run_plan = _validate_model(RunPlan, files["run-plan.json"], "run-plan.json")
    cells = _validate_collection(
        _CELLS_ADAPTER,
        files["cells.json"],
        "cells.json",
    )
    evidence = _validate_collection(
        _EVIDENCE_ADAPTER,
        files["evidence.json"],
        "evidence.json",
    )
    registry_path = release_dir / "metric-registry.json"
    metric_registry = (
        _validate_collection(
            _METRIC_REGISTRY_ADAPTER,
            registry_path.read_bytes(),
            "metric-registry.json",
        )
        if registry_path.is_file()
        else ()
    )
    _validate_json_object(files["release.json"], "release.json")

    if sha256_digest(files["run-plan.json"]) != release.run_plan_digest:
        raise ReleaseReplayError("run-plan.json digest does not match release input")
    if run_plan.suite_fingerprint != release.suite_fingerprint:
        raise ReleaseReplayError(
            "run-plan.json suite fingerprint does not match release input"
        )
    if run_plan.cap_sources != release.cap_sources:
        raise ReleaseReplayError("run-plan CAP provenance does not match release input")
    if (run_plan.cap_id, run_plan.cap_version) != (release.cap_id, release.cap_version):
        raise ReleaseReplayError("run-plan CAP identity does not match release input")
    if release.cap_sources:
        for source in release.cap_sources:
            contracts_path = _snapshot_contracts_path(
                harbor_contracts_path or _find_harbor_contracts(release_dir),
                source.catalog_snapshot_digest,
            )
            try:
                validate_harbor_source(source, contracts_path)
            except HarborSnapshotError as exc:
                raise ReleaseReplayError("Harbor CAP provenance is invalid") from exc
    _validate_cell_topology(run_plan.cells, cells)
    _validate_run_keys(run_plan)
    _validate_public_evidence_manifest(release_dir, evidence)

    try:
        rebuilt = build_release(
            release,
            cells,
            evidence,
            require_attribution=True,
            metric_registry=metric_registry,
        )
    except ReleaseGateError as exc:
        raise ReleaseReplayError(
            f"release replay input validation failed: {exc}"
        ) from exc
    except ValueError as exc:
        raise ReleaseReplayError("release replay input validation failed") from exc
    published = files["release.json"]
    if rebuilt != published:
        raise ReleaseReplayError("rebuilt release does not match release.json")

    published_digest = release_digest(published)
    if release_dir.name != release.release_id:
        raise ReleaseReplayError("release directory name does not match release ID")
    if expected_digest is not None and published_digest != expected_digest:
        raise ReleaseReplayError(
            "published release digest does not match expected digest"
        )
    return ReplayResult(
        release_id=release.release_id,
        published_digest=published_digest,
        expected_digest_verified=expected_digest is not None,
    )


def _find_harbor_contracts(release_dir: Path) -> Path | None:
    for ancestor in (release_dir, *release_dir.parents):
        candidate = ancestor / "harbor_catalog" / "contracts.json"
        if candidate.is_file():
            return candidate
    return None


def _snapshot_contracts_path(
    contracts_path: Path | None, snapshot_digest: str
) -> Path | None:
    if contracts_path is None:
        return None
    snapshot = contracts_path.parent / "snapshots" / snapshot_digest / "contracts.json"
    if snapshot.is_file():
        return snapshot
    return contracts_path


def _read_required_file(release_dir: Path, filename: str) -> bytes:
    path = release_dir / filename
    if not path.is_file():
        raise ReleaseReplayError(f"missing release replay file: {filename}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ReleaseReplayError(
            f"cannot read release replay file: {filename}"
        ) from exc


def _validate_model[ModelT: BaseModel](
    model: type[ModelT],
    content: bytes,
    filename: str,
) -> ModelT:
    try:
        return model.model_validate_json(content)
    except (ValidationError, ValueError) as exc:
        raise ReleaseReplayError(f"invalid release replay file: {filename}") from exc


def _validate_collection[ItemT](
    adapter: TypeAdapter[tuple[ItemT, ...]],
    content: bytes,
    filename: str,
) -> tuple[ItemT, ...]:
    try:
        return adapter.validate_json(content)
    except (ValidationError, ValueError) as exc:
        raise ReleaseReplayError(f"invalid release replay file: {filename}") from exc


def _validate_json_object(content: bytes, filename: str) -> dict[str, Any]:
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseReplayError(f"invalid release replay file: {filename}") from exc
    if not isinstance(document, dict):
        raise ReleaseReplayError(f"invalid release replay file: {filename}")
    return document


def _validate_cell_topology(
    planned_cells: tuple[RunCell, ...],
    terminal_cells: tuple[RunCell, ...],
) -> None:
    planned_by_key = {cell.run_key: cell for cell in planned_cells}
    terminal_by_key = {cell.run_key: cell for cell in terminal_cells}
    if (
        len(planned_by_key) != len(planned_cells)
        or len(terminal_by_key) != len(terminal_cells)
        or planned_by_key.keys() != terminal_by_key.keys()
    ):
        raise ReleaseReplayError(
            "run-plan.json cell topology does not match terminal cells"
        )
    for run_key, planned in planned_by_key.items():
        terminal = terminal_by_key[run_key]
        if planned.model_dump(exclude=_EXECUTION_FIELDS) != terminal.model_dump(
            exclude=_EXECUTION_FIELDS
        ):
            raise ReleaseReplayError(
                "run-plan.json cell identity does not match terminal cells"
            )


def _validate_run_keys(run_plan: RunPlan) -> None:
    for cell in run_plan.cells:
        expected_state = (
            CellState.PLANNED if cell.applicable else CellState.NOT_APPLICABLE
        )
        if cell.state is not expected_state:
            raise ReleaseReplayError("run-plan.json contains an invalid planned state")
        expected_key = canonical_run_key(
            run_plan.suite_id,
            run_plan.suite_fingerprint,
            case_id=cell.case_id,
            provider_id=cell.provider_id,
            access_path_id=cell.access_path_id,
            mode=cell.mode,
            round_number=cell.round,
        )
        if cell.run_key != expected_key:
            raise ReleaseReplayError("run key does not match its cell identity")


def _validate_public_evidence_manifest(
    release_dir: Path, evidence: tuple[EvidenceBundle, ...]
) -> None:
    path = release_dir / _PUBLIC_EVIDENCE_MANIFEST
    if not path.is_file():
        return
    document = _validate_json_object(
        _read_required_file(release_dir, _PUBLIC_EVIDENCE_MANIFEST),
        _PUBLIC_EVIDENCE_MANIFEST,
    )
    entries = document.get("evidence")
    historical_layout = entries is None
    if historical_layout:
        entries = document.get("entries")
    if not isinstance(entries, list):
        raise ReleaseReplayError("public evidence manifest is invalid")
    expected = {
        item.evidence_id: (item.run_key, str(item.public_digest)) for item in evidence
    }
    observed: dict[str, tuple[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReleaseReplayError("public evidence manifest is invalid")
        evidence_id = entry.get("evidence_id")
        run_key = entry.get("run_key")
        relative_path = entry.get("path")
        digest = entry.get("public_digest")
        if (
            not isinstance(evidence_id, str)
            or (not historical_layout and not isinstance(run_key, str))
            or not isinstance(relative_path, str)
            or not isinstance(digest, str)
        ):
            raise ReleaseReplayError("public evidence manifest is invalid")
        if not historical_layout and not isinstance(run_key, str):
            raise ReleaseReplayError("public evidence manifest is invalid")
        artifact = (
            release_dir / relative_path
            if historical_layout
            else release_dir.parent.parent / relative_path
        )
        if not artifact.is_file() or not artifact.resolve().is_relative_to(
            release_dir.parent.parent.resolve()
        ):
            raise ReleaseReplayError("public evidence artifact is missing")
        if sha256_digest(artifact.read_bytes()) != digest:
            raise ReleaseReplayError("public evidence bytes digest mismatch")
        if evidence_id in observed:
            raise ReleaseReplayError("public evidence manifest has duplicate evidence")
        if historical_layout:
            expected_entry = expected.get(evidence_id)
            if expected_entry is None:
                raise ReleaseReplayError("public evidence manifest is invalid")
            observed[evidence_id] = (expected_entry[0], digest)
        else:
            run_key_text = run_key
            if not isinstance(run_key_text, str):
                raise ReleaseReplayError("public evidence manifest is invalid")
            observed[evidence_id] = (run_key_text, digest)
    if observed != expected:
        raise ReleaseReplayError("public evidence manifest does not match release")
