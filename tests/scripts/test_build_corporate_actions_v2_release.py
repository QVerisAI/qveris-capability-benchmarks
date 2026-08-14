from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from qveris_bench.cap_packs.corporate_actions.direct import (
    CorporateDirectResult,
    evaluate_corporate_action_document,
)
from qveris_bench.cap_packs.corporate_actions.models import (
    corporate_action_request_identity,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.evidence.store import PublicArtifactStore
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
)
from qveris_bench.execution.qveris import QverisExecutionEnvelope
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.fingerprint import canonical_json_bytes
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
    fingerprint: str,
    registry_digest: str,
    raw_digest: str,
    outcome: CorporateDirectResult,
    latency_ms: float | None = 10.0,
    cost_credits: float | None = 2.0,
) -> bytes:
    return (
        json.dumps(
            {
                "binding_id": binding.binding_id,
                "run_key": cell.run_key,
                "provider_id": binding.provider_id,
                "access_path_id": binding.access_path_id,
                "transport": binding.transport,
                "state": outcome.state,
                "facts": outcome.facts,
                "unmet_conditions": outcome.unmet_conditions,
                "failure_attribution": outcome.failure_attribution,
                "raw_digest": raw_digest,
                "binding_registry_digest": registry_digest,
                "extractor_version": "2.0.0",
                "suite_fingerprint": fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
                "latency_ms": latency_ms,
                "cost_credits": cost_credits,
                "github_run_id": str(GITHUB_RUN_ID),
                "github_sha": GITHUB_SHA,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _zip(path: Path, name: str, content: bytes) -> str:
    return _zip_entries(path, {name: content})


def _zip_entries(path: Path, entries: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return sha256_digest(path.read_bytes())


def _github_exports(
    tmp_path: Path,
    *,
    infra_binding_id: str | None = None,
    forge_infra_as_negative: bool = False,
    outer_error_binding_id: str | None = None,
    request_override_binding_id: str | None = None,
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
        case = cases[cell.case_id]
        provider_payload = _provider_payload(
            str(binding.provider_id), case, binding.binding_id == infra_binding_id
        )
        outer_error = binding.binding_id == outer_error_binding_id
        response_status_code = 403 if outer_error else 200
        raw_document = (
            {"error": "entitlement required"}
            if outer_error
            else {"elapsed_time_ms": 10.0, "cost": 2.0, "result": provider_payload}
        )
        raw_bytes = json.dumps(raw_document, sort_keys=True).encode()
        response_digest = sha256_digest(raw_bytes)
        envelope = QverisExecutionEnvelope(
            artifact_id=f"{evidence_id}-search",
            tool_id=binding.tool_id,
            search_id="search-123",
            parameters=(
                {"symbol": "AAPL"}
                if binding.binding_id == request_override_binding_id
                else binding.parameters
            ),
            response_status_code=response_status_code,
            response_digest=response_digest,
        )
        envelope_bytes = canonical_json_bytes(envelope.model_dump(mode="json"))
        envelope_digest = sha256_digest(envelope_bytes)
        evaluation_payload = (
            {"status_code": response_status_code, "data": raw_document}
            if outer_error
            else provider_payload
        )
        outcome = evaluate_corporate_action_document(
            str(binding.provider_id),
            evaluation_payload,
            case,
            request_identity=corporate_action_request_identity(
                binding.request_identity
            ),
        )
        if forge_infra_as_negative and binding.binding_id == infra_binding_id:
            outcome = CorporateDirectResult(
                CellState.PROVIDER_NEGATIVE,
                {},
                tuple(case.completion_conditions),
                FailureAttribution.EMPTY_OR_PARTIAL_DATA,
            )
        terminal_record = public_store.persist(
            evidence_id,
            _terminal_bytes(
                binding,
                cell,
                compiled.fingerprint,
                direct_binding_registry_digest(registry_path),
                envelope_digest,
                outcome,
                None if outer_error else 10.0,
                None if outer_error else 2.0,
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
                "digest": _zip_entries(
                    private_zip,
                    {
                        f"{evidence_id}-search-execute-"
                        f"{response_digest.removeprefix('sha256:')}.json": raw_bytes,
                        f"{evidence_id}-search-execution-envelope-"
                        f"{envelope_digest.removeprefix('sha256:')}.json": (
                            envelope_bytes
                        ),
                    },
                ),
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


def _provider_payload(provider_id, case, infra_blocked: bool):
    if infra_blocked:
        return {"status_code": 429, "data": "rate limited"}
    if case.negative_control:
        return {"status_code": 404, "data": "Symbol not found"}
    event_date = str(case.input["start_date"])
    symbol = str(case.input["symbol"])
    if provider_id == "eodhd":
        data = f'Date,"Stock Splits"\n{event_date},\n'
    elif provider_id == "twelve-data":
        data = {"meta": {"symbol": symbol}, "splits": [{"date": event_date}]}
    elif provider_id == "alpha-vantage":
        data = {"symbol": symbol, "data": [{"effective_date": event_date}]}
    elif provider_id == "massive-stocks":
        data = {"results": [{"ticker": symbol, "execution_date": event_date}]}
    else:
        raise AssertionError("unsupported synthetic provider")
    return {"status_code": 200, "data": data}


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
    assert all(
        '"cost_credits"' not in path.read_text(encoding="utf-8")
        for path in evidence.glob("*.json")
    )
    assert '"cost_credits"' not in release.read_text(encoding="utf-8")


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
            tmp_path / "published/releases/corporate-actions-v2-test/cells.json"
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


def test_build_release_rejects_public_outcome_forged_against_private_raw(
    tmp_path: Path,
) -> None:
    binding_id = "twelve-data-invalid-corporate-actions-symbol-v2"
    run_export, artifact_export, archives = _github_exports(
        tmp_path,
        infra_binding_id=binding_id,
        forge_infra_as_negative=True,
    )

    with pytest.raises(ValueError, match="private raw outcome"):
        build_release_from_artifacts(
            run_export,
            artifact_export,
            archives,
            tmp_path / "published",
            suite_name="baseline",
            release_id="corporate-actions-v2-test",
        )


def test_build_release_preserves_outer_http_entitlement_terminal(
    tmp_path: Path,
) -> None:
    binding_id = "twelve-data-invalid-corporate-actions-symbol-v2"
    run_export, artifact_export, archives = _github_exports(
        tmp_path, outer_error_binding_id=binding_id
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
            tmp_path / "published/releases/corporate-actions-v2-test/cells.json"
        ).read_text()
    )
    blocked = [
        cell
        for cell in cells
        if cell["provider_id"] == "twelve-data"
        and cell["case_id"] == "invalid-corporate-actions-symbol-v2"
    ]
    assert len(blocked) == 3
    assert all(cell["state"] == "infra_blocked" for cell in blocked)
    assert all(cell["failure_attribution"] == "auth_or_entitlement" for cell in blocked)


def test_build_release_rejects_private_request_identity_swap(tmp_path: Path) -> None:
    binding_id = "twelve-data-invalid-corporate-actions-symbol-v2"
    run_export, artifact_export, archives = _github_exports(
        tmp_path, request_override_binding_id=binding_id
    )

    with pytest.raises(ValueError, match="request identity mismatch"):
        build_release_from_artifacts(
            run_export,
            artifact_export,
            archives,
            tmp_path / "published",
            suite_name="baseline",
            release_id="corporate-actions-v2-test",
        )
