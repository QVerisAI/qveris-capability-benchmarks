from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from qveris_bench.cap_packs.corporate_actions.direct import (
    evaluate_corporate_action_document,
    validate_public_outcome,
)
from qveris_bench.cap_packs.corporate_actions.models import (
    corporate_action_request_identity,
    validate_corporate_action_request_identities,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.execution.qveris import gateway_metrics
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.github_exports import (
    json_object,
    nested,
    private_execution_document,
    verified_archive,
)
from qveris_bench.releases.public_terminal import (
    PublicTerminal,
    assemble_public_terminal_release,
)
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.fingerprint import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs/corporate-actions/v2"
REPOSITORY = "QVerisAI/qveris-capability-benchmarks"


def build_release_from_artifacts(
    github_run_export: Path,
    github_artifacts_export: Path,
    artifact_archive_root: Path,
    output_root: Path,
    *,
    suite_name: str,
    release_id: str,
) -> str:
    if suite_name not in {"baseline", "market"}:
        raise ValueError("suite must be baseline or market")
    run = json_object(github_run_export)
    expected_workflow = f".github/workflows/live-corporate-actions-{suite_name}-e2e.yml"
    if (
        run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("event") != "workflow_dispatch"
        or run.get("path") != expected_workflow
        or nested(run, "repository", "full_name") != REPOSITORY
        or not isinstance(run.get("id"), int)
        or not isinstance(run.get("head_sha"), str)
    ):
        raise ValueError("GitHub run export does not match the trusted workflow")
    github_run_id = str(run["id"])
    github_sha = str(run["head_sha"])

    suite_path = PACK / f"{suite_name}-suite.yaml"
    cases_path = PACK / f"{suite_name}-cases.yaml"
    registry_path = PACK / f"{suite_name}-direct-bindings.json"
    evidence_dir = output_root / "evidence" / release_id
    release_dir = output_root / "releases" / release_id
    if evidence_dir.exists() or release_dir.exists():
        raise ValueError("release ID already exists; releases are immutable")
    compiled = compile_suite(
        suite_path, cases_path, ROOT / "providers", PACK / "cap.yaml"
    )
    registry = load_direct_binding_registry(registry_path)
    validate_direct_binding_registry(
        registry,
        suite_path,
        cases_path,
        ROOT / "providers",
        cap_path=PACK / "cap.yaml",
    )
    validate_corporate_action_request_identities(registry, compiled)
    cells = {cell.run_key: cell for cell in compiled.run_plan.cells if cell.applicable}
    bindings_by_cell = {
        (binding.case_id, binding.access_path_id): binding
        for binding in registry.bindings
    }
    cases = {case.case_id: case for case in compiled.cases}
    evidence_ids = set()
    for cell in cells.values():
        binding = bindings_by_cell[(cell.case_id, cell.access_path_id)]
        evidence_ids.add(f"{binding.binding_id}-round-{cell.round}")

    artifact_export = json_object(github_artifacts_export)
    artifact_rows = artifact_export.get("artifacts")
    if not isinstance(artifact_rows, list):
        raise ValueError("GitHub artifact export is missing artifacts")
    artifacts_by_name: dict[str, dict[str, Any]] = {}
    for item in artifact_rows:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("GitHub artifact export contains an invalid artifact")
        if item["name"] in artifacts_by_name:
            raise ValueError("GitHub artifact export contains duplicate names")
        artifacts_by_name[item["name"]] = item
    expected_names = {
        name
        for evidence_id in evidence_ids
        for name in (
            f"corporate-actions-{suite_name}-{evidence_id}",
            f"private-corporate-actions-{suite_name}-{evidence_id}",
        )
    }
    if artifacts_by_name.keys() != expected_names:
        raise ValueError("GitHub artifacts do not match the frozen matrix")

    terminals: dict[str, tuple[PublicTerminal, bytes]] = {}
    attested_artifacts = []
    for evidence_id in sorted(evidence_ids):
        public_name = f"corporate-actions-{suite_name}-{evidence_id}"
        private_name = f"private-corporate-actions-{suite_name}-{evidence_id}"
        public_row = artifacts_by_name[public_name]
        private_row = artifacts_by_name[private_name]
        public_entries, public_archive_digest = verified_archive(
            public_row, artifact_archive_root
        )
        private_entries, private_archive_digest = verified_archive(
            private_row, artifact_archive_root
        )
        if len(public_entries) != 1:
            raise ValueError("public artifact must contain exactly one terminal")
        public_path, public_bytes = next(iter(public_entries.items()))
        public_digest = sha256_digest(public_bytes)
        suffix = public_digest.removeprefix("sha256:")
        if PurePosixPath(public_path).name != f"{evidence_id}-{suffix}.json":
            raise ValueError("public artifact filename does not bind its digest")
        try:
            terminal = PublicTerminal.model_validate_json(public_bytes)
        except ValueError as exc:
            raise ValueError("public artifact is not a terminal") from exc
        matched_cell = cells.get(terminal.run_key)
        if (
            matched_cell is None
            or evidence_id != f"{terminal.binding_id}-round-{matched_cell.round}"
            or terminal.github_run_id != github_run_id
            or terminal.github_sha != github_sha
        ):
            raise ValueError("public terminal provenance or cell identity mismatch")
        binding = bindings_by_cell[(matched_cell.case_id, matched_cell.access_path_id)]
        if binding.binding_id != terminal.binding_id:
            raise ValueError("public terminal binding identity mismatch")
        raw_document, execution_envelope = private_execution_document(
            private_entries,
            evidence_id,
            terminal.raw_digest,
            binding.tool_id,
            binding.parameters,
        )
        payload: dict[str, Any]
        if execution_envelope.response_status_code >= 400:
            payload = {
                "status_code": execution_envelope.response_status_code,
                "data": raw_document,
            }
        else:
            result_payload = raw_document.get("result")
            if not isinstance(result_payload, dict):
                raise ValueError("private raw execution is missing result")
            payload = result_payload
        case = cases[binding.case_id]
        raw_outcome = evaluate_corporate_action_document(
            str(binding.provider_id),
            payload,
            case,
            request_identity=corporate_action_request_identity(
                binding.request_identity
            ),
        )
        if (
            terminal.state is not raw_outcome.state
            or terminal.facts != raw_outcome.facts
            or terminal.unmet_conditions != raw_outcome.unmet_conditions
            or terminal.failure_attribution is not raw_outcome.failure_attribution
        ):
            raise ValueError("public terminal does not match private raw outcome")
        latency_ms, cost_credits = gateway_metrics(raw_document)
        if terminal.latency_ms != latency_ms or terminal.cost_credits not in (
            None,
            cost_credits,
        ):
            raise ValueError(
                "public terminal metrics do not match private raw evidence"
            )
        published_terminal = terminal.model_copy(update={"cost_credits": None})
        published_bytes = (
            json.dumps(
                published_terminal.model_dump(mode="json", exclude={"cost_credits"}),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        published_digest = sha256_digest(published_bytes)
        terminals[evidence_id] = published_terminal, published_bytes
        attested_artifacts.append(
            {
                "name": evidence_id,
                "public_artifact_id": public_row["id"],
                "public_archive_digest": public_archive_digest,
                "private_artifact_id": private_row["id"],
                "private_archive_digest": private_archive_digest,
                "source_public_digest": public_digest,
                "public_digest": published_digest,
                "raw_digest": terminal.raw_digest,
            }
        )

    attestation = {
        "source": "github_actions_api",
        "repository": REPOSITORY,
        "workflow_path": expected_workflow,
        "github_run_id": github_run_id,
        "github_sha": github_sha,
        "artifacts": attested_artifacts,
    }
    attestation_bytes = canonical_json_bytes(attestation)
    provenance = {
        evidence_id: (sha256_digest(source_bytes), terminal.raw_digest)
        for evidence_id, (terminal, source_bytes) in terminals.items()
    }
    limitations = (
        "This release measures the frozen split-event workflow only.",
        "Provider and Access Path conclusions apply only to the released cells.",
        "Provider-negative is not evidence that a Provider never supports a market.",
        "Offline replay does not call QVeris or a data Provider.",
    )
    with tempfile.TemporaryDirectory(prefix="corporate-actions-v2-release-") as temp:
        terminal_paths = []
        for evidence_id, (_, source_bytes) in sorted(terminals.items()):
            target = Path(temp) / f"{evidence_id}.json"
            target.write_bytes(source_bytes)
            terminal_paths.append(target)
        release_artifacts = assemble_public_terminal_release(
            compiled=compiled,
            binding_registry=registry,
            binding_registry_digest=direct_binding_registry_digest(registry_path),
            terminal_paths=tuple(terminal_paths),
            release_id=release_id,
            version="2.0.0",
            limitations=limitations,
            outcome_validator=validate_public_outcome,
            expected_github_run_id=github_run_id,
            expected_github_sha=github_sha,
            expected_provenance=provenance,
            github_artifacts_manifest_bytes=attestation_bytes,
            binding_registry_bytes=registry_path.read_bytes(),
        )
    evidence_dir.mkdir(parents=True)
    for evidence_id, (_, source_bytes) in sorted(terminals.items()):
        (evidence_dir / f"{evidence_id}.json").write_bytes(source_bytes)
    release_artifacts.write(release_dir)
    (release_dir / "github-artifacts.json").write_bytes(attestation_bytes)
    return release_digest(release_artifacts.release_bytes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-run-export", type=Path, required=True)
    parser.add_argument("--github-artifacts-export", type=Path, required=True)
    parser.add_argument("--artifact-archive-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--suite", choices=("baseline", "market"), required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    digest = build_release_from_artifacts(
        args.github_run_export,
        args.github_artifacts_export,
        args.artifact_archive_root,
        args.output_root,
        suite_name=args.suite,
        release_id=args.release_id,
    )
    print(digest)


if __name__ == "__main__":
    main()
