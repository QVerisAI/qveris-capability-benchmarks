from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.enums import CellState
from qveris_bench.models.evidence import EvidenceBundle
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
_CELLS_ADAPTER = TypeAdapter(tuple[RunCell, ...])
_EVIDENCE_ADAPTER = TypeAdapter(tuple[EvidenceBundle, ...])
_EXECUTION_FIELDS = {"state", "failure_attribution"}
_LEGACY_RELEASE_DIGESTS_WITHOUT_ATTRIBUTION = frozenset(
    {
        "sha256:62df52047ecb0bcf66fce96a0240f97f29c1bc9e55066ca9e06ae0f878d00c0f",
        "sha256:a22d3dbcb47d094baac201a0c100e6ad87b6159d6780bdf29ea3c5f0e4a8abaf",
        "sha256:5a159d6e5777b3829e57f861e18182a76540d94dc1f3b8c23ae4410207e5024e",
        "sha256:7e7ff0ebf2c72e96e6bb1544c07da4195f82154378b686d544667b922d5a6e4b",
        "sha256:2984a796bee2e9242c818f3336927972fe93030ca13f01f459e7333d5d509f57",
        "sha256:f0535988872ec0b300de726a1ec3e6c28988ba39401ea6bdb04d8a739798f2b3",
    }
)


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
    _validate_json_object(files["release.json"], "release.json")

    if sha256_digest(files["run-plan.json"]) != release.run_plan_digest:
        raise ReleaseReplayError("run-plan.json digest does not match release input")
    if run_plan.suite_fingerprint != release.suite_fingerprint:
        raise ReleaseReplayError(
            "run-plan.json suite fingerprint does not match release input"
        )
    _validate_cell_topology(run_plan.cells, cells)
    _validate_run_keys(run_plan)

    try:
        rebuilt = build_release(
            release,
            cells,
            evidence,
            require_attribution=False,
        )
        if release_digest(rebuilt) not in _LEGACY_RELEASE_DIGESTS_WITHOUT_ATTRIBUTION:
            rebuilt = build_release(release, cells, evidence)
    except ReleaseGateError as exc:
        raise ReleaseReplayError(
            f"release replay input validation failed: {exc}"
        ) from exc
    except ValueError as exc:
        raise ReleaseReplayError("release replay input validation failed") from exc
    published = files["release.json"]
    if rebuilt != published:
        raise ReleaseReplayError("rebuilt release does not match release.json")
    if release.public_evidence_manifest_digest is not None:
        _validate_public_evidence_manifest(
            release_dir,
            release.public_evidence_manifest_digest,
            evidence,
        )

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


def _validate_public_evidence_manifest(
    release_dir: Path,
    expected_digest: str,
    evidence: tuple[EvidenceBundle, ...],
) -> None:
    content = _read_required_file(release_dir, "public-evidence-manifest.json")
    if sha256_digest(content) != expected_digest:
        raise ReleaseReplayError("public evidence manifest digest mismatch")
    document = _validate_json_object(content, "public-evidence-manifest.json")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ReleaseReplayError("invalid public evidence manifest entries")
    expected = {item.evidence_id: item for item in evidence}
    if {item.get("evidence_id") for item in entries if isinstance(item, dict)} != set(
        expected
    ):
        raise ReleaseReplayError("public evidence manifest topology mismatch")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReleaseReplayError("invalid public evidence manifest entry")
        evidence_id = entry["evidence_id"]
        item = expected[evidence_id]
        if (
            entry.get("public_digest") != item.public_digest
            or entry.get("raw_digest") != item.raw_digest
        ):
            raise ReleaseReplayError("public evidence manifest facts mismatch")
        path = (release_dir / str(entry.get("path"))).resolve()
        if not path.is_relative_to(release_dir.parents[1].resolve()):
            raise ReleaseReplayError("public evidence path escapes repository")
        try:
            public_bytes = path.read_bytes()
        except OSError as exc:
            raise ReleaseReplayError("missing public evidence bytes") from exc
        if sha256_digest(public_bytes) != item.public_digest:
            raise ReleaseReplayError("public evidence bytes digest mismatch")


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
