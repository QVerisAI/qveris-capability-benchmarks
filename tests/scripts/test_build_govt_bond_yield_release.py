from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from qveris_bench.cap_packs.govt_bond_yield.direct import (
    GovernmentBondDirectResult,
    evaluate_government_bond_document,
)
from qveris_bench.cap_packs.govt_bond_yield.models import (
    GovernmentBondRequestIdentity,
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
from scripts.build_govt_bond_yield_release import (
    PACK,
    REPOSITORY,
    build_release_from_artifacts,
)

GITHUB_RUN_ID = 987654
GITHUB_SHA = "a" * 40


def _zip(path: Path, entries: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return sha256_digest(path.read_bytes())


def _terminal_bytes(
    binding,
    cell,
    fingerprint: str,
    registry_digest: str,
    envelope_digest: str,
    outcome: GovernmentBondDirectResult,
    *,
    cost_credits: float | None = None,
    github_sha: str = GITHUB_SHA,
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
                "raw_digest": envelope_digest,
                "binding_registry_digest": registry_digest,
                "extractor_version": "1.0.0",
                "suite_fingerprint": fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
                "latency_ms": 10.0,
                "cost_credits": cost_credits,
                "github_run_id": str(GITHUB_RUN_ID),
                "github_sha": github_sha,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _provider_payload(provider_id: str, case) -> dict[str, object]:
    if case.negative_control:
        return {
            "status_code": 400,
            "data": {"error_message": "unsupported country"},
        }
    country = str(case.input["country"])
    contract = case.input["provider_identities"]
    if provider_id == "stlouisfed-fred":
        identity = contract["stlouisfed-fred-govt-bond-yield-qveris"]
        return {
            "status_code": 200,
            "data": {
                "seriess": [{"id": identity["vendor_identifier"]}],
                "observations": [{"date": "2024-12-31", "value": "4.5"}],
            },
        }
    symbol = (
        "10-Year Treasury Constant Maturity Rate"
        if country == "US"
        else f"{country}10Y"
    )
    return {
        "status_code": 200,
        "data": {
            "data": [
                {
                    "symbol": symbol,
                    "date": "2024-12-31",
                    "close": 4.5,
                    "unit": "percent",
                }
            ]
        },
    }


def _github_exports(
    tmp_path: Path,
    *,
    request_swap: bool = False,
    forge_outcome: bool = False,
    account_cost: bool = False,
    event: str = "workflow_dispatch",
) -> tuple[Path, Path, Path, Path | None]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    suite_path = PACK / "suite.yaml"
    cases_path = PACK / "cases.yaml"
    registry_path = PACK / "direct-bindings.json"
    compiled = compile_suite(
        suite_path,
        cases_path,
        PACK / "providers",
        PACK / "cap.yaml",
    )
    registry = load_direct_binding_registry(registry_path)
    bindings = {(item.case_id, item.access_path_id): item for item in registry.bindings}
    cases = {item.case_id: item for item in compiled.cases}
    archives = tmp_path / "archives"
    archives.mkdir()
    public_store = PublicArtifactStore(tmp_path / "public")
    artifacts = []
    artifact_id = 2000
    mutated = False
    for cell in compiled.run_plan.cells:
        if not cell.applicable:
            continue
        binding = bindings[(cell.case_id, cell.access_path_id)]
        case = cases[cell.case_id]
        evidence_id = f"{binding.binding_id}-round-{cell.round}"
        payload = _provider_payload(str(binding.provider_id), case)
        raw_document = {"elapsed_time_ms": 10.0, "cost": 2.0, "result": payload}
        raw_bytes = json.dumps(raw_document, sort_keys=True).encode()
        response_digest = sha256_digest(raw_bytes)
        parameters = dict(binding.parameters)
        if request_swap and not mutated:
            identity = GovernmentBondRequestIdentity.model_validate(
                binding.request_identity
            )
            parameters[identity.parameter_path[0]] = "WRONG"
            mutated = True
        envelope = QverisExecutionEnvelope(
            artifact_id=f"{evidence_id}-search",
            tool_id=binding.tool_id,
            search_id="search-123",
            parameters=parameters,
            response_status_code=200,
            response_digest=response_digest,
        )
        envelope_bytes = canonical_json_bytes(envelope.model_dump(mode="json"))
        envelope_digest = sha256_digest(envelope_bytes)
        outcome = evaluate_government_bond_document(
            str(binding.provider_id),
            payload,
            case,
            request_identity=GovernmentBondRequestIdentity.model_validate(
                binding.request_identity
            ),
        )
        if forge_outcome and not mutated:
            outcome = GovernmentBondDirectResult(
                CellState.PROVIDER_NEGATIVE,
                {},
                tuple(case.completion_conditions),
                FailureAttribution.EMPTY_OR_PARTIAL_DATA,
            )
            mutated = True
        terminal = public_store.persist(
            evidence_id,
            _terminal_bytes(
                binding,
                cell,
                compiled.fingerprint,
                direct_binding_registry_digest(registry_path),
                envelope_digest,
                outcome,
                cost_credits=2.0 if account_cost and not mutated else None,
                github_sha="c" * 40 if event == "pull_request" else GITHUB_SHA,
            ),
        )
        if account_cost and not mutated:
            mutated = True
        public_zip = archives / f"{artifact_id}.zip"
        artifacts.append(
            {
                "id": artifact_id,
                "name": f"govt-bond-yield-baseline-{evidence_id}",
                "digest": _zip(
                    public_zip,
                    {terminal.path.name: terminal.path.read_bytes()},
                ),
                "expired": False,
            }
        )
        artifact_id += 1
        private_zip = archives / f"{artifact_id}.zip"
        artifacts.append(
            {
                "id": artifact_id,
                "name": f"private-govt-bond-yield-baseline-{evidence_id}",
                "digest": _zip(
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
    run = {
        "id": GITHUB_RUN_ID,
        "head_sha": GITHUB_SHA,
        "status": "completed",
        "conclusion": "success",
        "event": event,
        "path": ".github/workflows/live-govt-bond-yield-baseline-e2e.yml",
        "repository": {"full_name": REPOSITORY},
    }
    merge_export = None
    if event == "pull_request":
        run["pull_requests"] = [{"base": {"sha": "b" * 40}}]
        merge_export = tmp_path / "merge.json"
        merge_export.write_text(
            json.dumps(
                {
                    "sha": "c" * 40,
                    "parents": [{"sha": GITHUB_SHA}, {"sha": "b" * 40}],
                }
            )
        )
    run_export = tmp_path / "run.json"
    run_export.write_text(json.dumps(run))
    artifact_export = tmp_path / "artifacts.json"
    artifact_export.write_text(json.dumps({"artifacts": artifacts}))
    return run_export, artifact_export, archives, merge_export


def _build(tmp_path: Path, **options: object) -> str:
    run, artifacts, archives, merge = _github_exports(tmp_path, **options)
    return build_release_from_artifacts(
        run,
        artifacts,
        archives,
        tmp_path / "published",
        suite_name="baseline",
        release_id="govt-bond-yield-test-v1",
        github_merge_commit_export=merge,
    )


def test_builder_verifies_synthetic_merge_and_excludes_account_costs(
    tmp_path: Path,
) -> None:
    digest = _build(tmp_path, event="pull_request")

    assert digest.startswith("sha256:")
    evidence = tmp_path / "published/evidence/govt-bond-yield-test-v1"
    assert len(tuple(evidence.glob("*.json"))) == 8
    assert all(
        b'"cost_credits"' not in path.read_bytes() for path in evidence.iterdir()
    )

    with pytest.raises(ValueError, match="already exists"):
        run, artifacts, archives, merge = _github_exports(
            tmp_path / "second", event="pull_request"
        )
        build_release_from_artifacts(
            run,
            artifacts,
            archives,
            tmp_path / "published",
            suite_name="baseline",
            release_id="govt-bond-yield-test-v1",
            github_merge_commit_export=merge,
        )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"request_swap": True}, "request identity mismatch"),
        ({"forge_outcome": True}, "does not match private raw outcome"),
        ({"account_cost": True}, "publication policy"),
    ],
)
def test_builder_rejects_tampered_execution_boundary(
    tmp_path: Path,
    options: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _build(tmp_path, **options)


def test_builder_rejects_an_incomplete_artifact_set(tmp_path: Path) -> None:
    run, artifact_export, archives, merge = _github_exports(tmp_path)
    document = json.loads(artifact_export.read_text())
    document["artifacts"].pop()
    artifact_export.write_text(json.dumps(document))

    with pytest.raises(ValueError, match="frozen matrix"):
        build_release_from_artifacts(
            run,
            artifact_export,
            archives,
            tmp_path / "published",
            suite_name="baseline",
            release_id="govt-bond-yield-test-v1",
            github_merge_commit_export=merge,
        )
