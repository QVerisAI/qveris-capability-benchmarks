from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import release_digest

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

    try:
        rebuilt = build_release(
            release,
            cells,
            evidence,
            require_attribution=False,
        )
    except ValueError as exc:
        raise ReleaseReplayError("release replay input validation failed") from exc
    published = files["release.json"]
    if rebuilt != published:
        raise ReleaseReplayError("rebuilt release does not match release.json")

    published_digest = release_digest(published)
    if expected_digest is not None and published_digest != expected_digest:
        raise ReleaseReplayError(
            "published release digest does not match expected digest"
        )
    return ReplayResult(
        release_id=release.release_id,
        published_digest=published_digest,
        expected_digest_verified=expected_digest is not None,
    )


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
