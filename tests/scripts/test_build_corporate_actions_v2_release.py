from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.evidence.store import PublicArtifactStore
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
)
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.suites.compiler import compile_suite
from scripts.build_corporate_actions_v2_release import (
    PACK,
    REPOSITORY,
    ROOT,
    build_release_from_artifacts,
)

GITHUB_RUN_ID = 123456
GITHUB_SHA = "a" * 40


def _terminal_bytes(
    binding,
    cell,
    case,
    fingerprint: str,
    registry_digest: str,
    raw_digest: str,
    *,
    infra_blocked: bool = False,
) -> bytes:
    if infra_blocked:
        state = CellState.INFRA_BLOCKED
        facts = {"execution_failure": "rate_limited"}
        unmet_conditions = list(case.completion_conditions)
        attribution = FailureAttribution.RATE_LIMITED
    elif case.negative_control:
        state = CellState.COMPLETED
        facts = {"validation_error": "provider_validation_error"}
        unmet_conditions = []
        attribution = FailureAttribution.PROVIDER_VALIDATION_ERROR
    else:
        state = CellState.COMPLETED
        facts = {
            "symbol": case.input["symbol"],
            "identity_verified": True,
            "identity_basis": "request_bound",
            "action_type": "split",
            "date": str(case.input["start_date"]),
        }
        unmet_conditions = []
        attribution = None
    return (
        json.dumps(
            {
                "binding_id": binding.binding_id,
                "run_key": cell.run_key,
                "provider_id": binding.provider_id,
                "access_path_id": binding.access_path_id,
                "transport": binding.transport,
                "state": state,
                "facts": facts,
                "unmet_conditions": unmet_conditions,
                "failure_attribution": attribution,
                "raw_digest": raw_digest,
                "binding_registry_digest": registry_digest,
                "extractor_version": "2.0.0",
                "suite_fingerprint": fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
                "latency_ms": 10.0,
                "cost_credits": 2.0,
                "github_run_id": str(GITHUB_RUN_ID),
                "github_sha": GITHUB_SHA,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _zip(path: Path, name: str, content: bytes) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    return sha256_digest(path.read_bytes())


def _github_exports(
    tmp_path: Path, *, infra_binding_id: str | None = None
) -> tuple[Path, Path, Path]:
    suite_path = PACK / "baseline-suite.yaml"
    cases_path = PACK / "baseline-cases.yaml"
    registry_path = PACK / "baseline-direct-bindings.json"
    compiled = compile_suite(
        suite_path, cases_path, ROOT / "providers", PACK / "cap.yaml"
    )
    registry = load_direct_binding_registry(registry_path)
    bindings = {(item.case_id, item.access_path_id): item for item in registry.bindings}
    cases = {item.case_id: item for item in compiled.cases}
    archives = tmp_path / "archives"
    archives.mkdir()
    public_store = PublicArtifactStore(tmp_path / "public-files")
    artifact_rows = []
    artifact_id = 1000
    for cell in compiled.run_plan.cells:
        if not cell.applicable:
            continue
        binding = bindings[(cell.case_id, cell.access_path_id)]
        evidence_id = f"{binding.binding_id}-round-{cell.round}"
        raw_bytes = json.dumps({"run_key": cell.run_key}, sort_keys=True).encode()
        raw_digest = sha256_digest(raw_bytes)
        terminal_record = public_store.persist(
            evidence_id,
            _terminal_bytes(
                binding,
                cell,
                cases[cell.case_id],
                compiled.fingerprint,
                direct_binding_registry_digest(registry_path),
                raw_digest,
                infra_blocked=binding.binding_id == infra_binding_id,
            ),
        )
        public_name = f"corporate-actions-baseline-{evidence_id}"
        public_zip = archives / f"{artifact_id}.zip"
        artifact_rows.append(
            {
                "id": artifact_id,
                "name": public_name,
                "digest": _zip(
                    public_zip,
                    terminal_record.path.name,
                    terminal_record.path.read_bytes(),
                ),
                "expired": False,
            }
        )
        artifact_id += 1
        private_name = f"private-corporate-actions-baseline-{evidence_id}"
        private_zip = archives / f"{artifact_id}.zip"
        artifact_rows.append(
            {
                "id": artifact_id,
                "name": private_name,
                "digest": _zip(private_zip, "execute.json", raw_bytes),
                "expired": False,
            }
        )
        artifact_id += 1
    run_export = tmp_path / "run.json"
    run_export.write_text(
        json.dumps(
            {
                "id": GITHUB_RUN_ID,
                "head_sha": GITHUB_SHA,
                "status": "completed",
                "conclusion": "success",
                "event": "workflow_dispatch",
                "path": ".github/workflows/live-corporate-actions-baseline-e2e.yml",
                "repository": {"full_name": REPOSITORY},
            }
        )
    )
    artifact_export = tmp_path / "artifacts.json"
    artifact_export.write_text(json.dumps({"artifacts": artifact_rows}))
    return run_export, artifact_export, archives


def test_build_release_verifies_github_archives_and_private_raw(
    tmp_path: Path,
) -> None:
    run_export, artifact_export, archives = _github_exports(tmp_path)

    digest = build_release_from_artifacts(
        run_export,
        artifact_export,
        archives,
        tmp_path / "published",
        suite_name="baseline",
        release_id="corporate-actions-v2-test",
    )

    assert digest.startswith("sha256:")
    release = tmp_path / "published/releases/corporate-actions-v2-test/release.json"
    assert release.is_file()
    evidence = tmp_path / "published/evidence/corporate-actions-v2-test"
    assert len(list(evidence.glob("*.json"))) == 24


def test_build_release_rejects_missing_private_raw_digest(tmp_path: Path) -> None:
    run_export, artifact_export, archives = _github_exports(tmp_path)
    document = json.loads(artifact_export.read_text())
    private = next(
        item for item in document["artifacts"] if item["name"].startswith("private-")
    )
    archive_path = archives / f"{private['id']}.zip"
    private["digest"] = _zip(archive_path, "execute.json", b"tampered")
    artifact_export.write_text(json.dumps(document))

    with pytest.raises(ValueError, match="private raw artifact"):
        build_release_from_artifacts(
            run_export,
            artifact_export,
            archives,
            tmp_path / "published",
            suite_name="baseline",
            release_id="corporate-actions-v2-test",
        )


def test_build_release_preserves_attested_infra_blocked_terminal(
    tmp_path: Path,
) -> None:
    binding_id = "twelve-data-invalid-corporate-actions-symbol-v2"
    run_export, artifact_export, archives = _github_exports(
        tmp_path, infra_binding_id=binding_id
    )

    build_release_from_artifacts(
        run_export,
        artifact_export,
        archives,
        tmp_path / "published",
        suite_name="baseline",
        release_id="corporate-actions-v2-test",
    )

    cells = json.loads(
        (
            tmp_path
            / "published/releases/corporate-actions-v2-test/cells.json"
        ).read_text()
    )
    blocked = [
        cell
        for cell in cells
        if cell["state"] == "infra_blocked"
        and cell["case_id"] == "invalid-corporate-actions-symbol-v2"
        and cell["provider_id"] == "twelve-data"
    ]
    assert len(blocked) == 3
    assert all(cell["failure_attribution"] == "rate_limited" for cell in blocked)
