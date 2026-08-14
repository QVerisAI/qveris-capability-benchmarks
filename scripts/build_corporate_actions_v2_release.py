from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from qveris_bench.cap_packs.corporate_actions.direct import validate_public_outcome
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.public_terminal import (
    PublicTerminal,
    assemble_public_terminal_release,
)
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.fingerprint import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs/corporate-actions/v2"


def build_release_from_artifacts(
    artifact_root: Path,
    output_root: Path,
    *,
    suite_name: str,
    release_id: str,
    expected_github_run_id: str,
    expected_github_sha: str,
) -> str:
    if suite_name not in {"baseline", "market"}:
        raise ValueError("suite must be baseline or market")
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
    cells = {cell.run_key: cell for cell in compiled.run_plan.cells if cell.applicable}
    bindings_by_cell = {
        (binding.case_id, binding.access_path_id): binding
        for binding in registry.bindings
    }
    expected_evidence_ids = set()
    for cell in cells.values():
        binding = bindings_by_cell[(cell.case_id, cell.access_path_id)]
        expected_evidence_ids.add(f"{binding.binding_id}-round-{cell.round}")
    terminals: dict[str, tuple[PublicTerminal, bytes]] = {}
    for source_path in sorted(artifact_root.rglob("*.json")):
        source_bytes = source_path.read_bytes()
        try:
            terminal = PublicTerminal.model_validate_json(source_bytes)
        except ValueError as exc:
            raise ValueError(
                f"artifact is not a public terminal: {source_path}"
            ) from exc
        matched_cell = cells.get(terminal.run_key)
        if matched_cell is None:
            raise ValueError("artifact terminal does not match an applicable run key")
        evidence_id = f"{terminal.binding_id}-round-{matched_cell.round}"
        suffix = sha256_digest(source_bytes).removeprefix("sha256:")
        if source_path.name != f"{evidence_id}-{suffix}.json":
            raise ValueError(
                "artifact filename does not bind its evidence ID and digest"
            )
        if evidence_id in terminals:
            raise ValueError("duplicate public terminal artifact")
        terminals[evidence_id] = terminal, source_bytes
    if terminals.keys() != expected_evidence_ids:
        raise ValueError("public terminal artifacts do not match the frozen matrix")
    attestation = {
        "github_run_id": expected_github_run_id,
        "github_sha": expected_github_sha,
        "artifacts": [
            {
                "name": evidence_id,
                "public_digest": sha256_digest(source_bytes),
                "raw_digest": terminal.raw_digest,
            }
            for evidence_id, (terminal, source_bytes) in sorted(terminals.items())
        ],
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
        artifacts = assemble_public_terminal_release(
            compiled=compiled,
            binding_registry=registry,
            binding_registry_digest=direct_binding_registry_digest(registry_path),
            terminal_paths=tuple(terminal_paths),
            release_id=release_id,
            version="2.0.0",
            limitations=limitations,
            outcome_validator=validate_public_outcome,
            expected_github_run_id=expected_github_run_id,
            expected_github_sha=expected_github_sha,
            expected_provenance=provenance,
            github_artifacts_manifest_bytes=attestation_bytes,
            binding_registry_bytes=registry_path.read_bytes(),
        )
    evidence_dir.mkdir(parents=True)
    for evidence_id, (_, source_bytes) in sorted(terminals.items()):
        (evidence_dir / f"{evidence_id}.json").write_bytes(source_bytes)
    artifacts.write(release_dir)
    (release_dir / "github-artifacts.json").write_bytes(attestation_bytes)
    return release_digest(artifacts.release_bytes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--suite", choices=("baseline", "market"), required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-sha", required=True)
    args = parser.parse_args()
    digest = build_release_from_artifacts(
        args.artifact_root,
        args.output_root,
        suite_name=args.suite,
        release_id=args.release_id,
        expected_github_run_id=args.github_run_id,
        expected_github_sha=args.github_sha,
    )
    print(digest)


if __name__ == "__main__":
    main()
