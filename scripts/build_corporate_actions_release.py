from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qveris_bench.cap_packs.corporate_actions.direct import (
    evaluate,
    validate_public_outcome,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.models.enums import DisclosureLevel, LicenseStatus, RedactionStatus
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.public_terminal import (
    PublicTerminal,
    assemble_public_terminal_release,
)
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.fingerprint import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs/corporate-actions"
LIMITATIONS = (
    (
        "This release measures historical US-equity stock-split retrieval for AAPL and "
        "one invalid-symbol control through the frozen QVeris Access Paths."
    ),
    (
        "Positive evidence proves required split fields for the frozen sample; "
        "it does not establish provider-wide corporate-actions coverage."
    ),
    (
        "A provider-negative invalid control means no explicit validation "
        "error was returned in observed rounds; it is not support evidence."
    ),
    (
        "Offline replay verifies released evidence and provenance without "
        "calling QVeris or a provider."
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--suite", type=Path, default=PACK / "suite.yaml")
    parser.add_argument("--cases", type=Path, default=PACK / "cases.yaml")
    parser.add_argument("--bindings", type=Path, default=PACK / "direct-bindings.json")
    args = parser.parse_args()
    evidence_dir = ROOT / "evidence" / args.release_id
    output_dir = ROOT / "releases" / args.release_id
    if evidence_dir.exists() or output_dir.exists():
        raise ValueError("release ID already exists; releases are immutable")

    compiled = compile_suite(
        args.suite, args.cases, ROOT / "providers", PACK / "cap.yaml"
    )
    registry_path = args.bindings
    registry = load_direct_binding_registry(registry_path)
    validate_direct_binding_registry(
        registry,
        args.suite,
        args.cases,
        ROOT / "providers",
        cap_path=PACK / "cap.yaml",
    )
    summary = _load_summary(
        args.summary,
        expected_count=sum(cell.applicable for cell in compiled.run_plan.cells),
    )
    bindings = {(item.case_id, item.access_path_id): item for item in registry.bindings}
    cases = {item.case_id: item for item in compiled.cases}
    evidence_dir.mkdir(parents=True)
    terminals: list[Path] = []
    for cell in compiled.run_plan.cells:
        if not cell.applicable:
            continue
        binding = bindings[(cell.case_id, cell.access_path_id)]
        entry = summary[(cell.provider_id, cell.case_id, cell.round)]
        raw_path = (
            args.raw_root / f"{cell.provider_id}-{cell.case_id}-round-{cell.round}.json"
        )
        raw_bytes = raw_path.read_bytes()
        raw_digest = sha256_digest(raw_bytes)
        if entry["raw_digest"] != raw_digest:
            raise ValueError(f"raw digest mismatch for {cell.run_key}")
        raw = json.loads(raw_bytes)
        result = raw.get("result")
        if not isinstance(result, dict):
            raise ValueError(f"missing result for {cell.run_key}")
        terminal_outcome = evaluate(cell.provider_id, cell.case_id, result)
        expected_probe_state = (
            "passed" if terminal_outcome.state.value == "completed" else "failed"
        )
        if entry["state"] != expected_probe_state:
            raise ValueError(f"probe state mismatch for {cell.run_key}")
        terminal = PublicTerminal(
            binding_id=binding.binding_id,
            run_key=cell.run_key,
            provider_id=cell.provider_id,
            access_path_id=cell.access_path_id,
            transport=binding.transport,
            state=terminal_outcome.state,
            facts=terminal_outcome.facts,
            unmet_conditions=(
                ()
                if terminal_outcome.state.value == "completed"
                else ("provider_validation_error",)
            ),
            failure_attribution=terminal_outcome.attribution,
            raw_digest=raw_digest,
            binding_registry_digest=direct_binding_registry_digest(registry_path),
            extractor_version="1.0.0",
            suite_fingerprint=compiled.fingerprint,
            redaction_status=RedactionStatus.SANITIZED,
            disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
            license_status=LicenseStatus.CLEARED,
            latency_ms=entry["latency_ms"],
            cost_credits=entry["cost_credits"],
            github_run_id=args.github_run_id,
            github_sha=args.github_sha,
        )
        outcome = validate_public_outcome(cases[cell.case_id], binding, terminal.facts)
        if (
            terminal.state,
            terminal.unmet_conditions,
            terminal.failure_attribution,
        ) != (outcome.state, outcome.unmet_conditions, outcome.failure_attribution):
            raise ValueError(f"CAP evaluation mismatch for {cell.run_key}")
        evidence_id = f"{binding.binding_id}-round-{cell.round}"
        path = evidence_dir / f"{evidence_id}.json"
        path.write_bytes(
            canonical_json_bytes(terminal.model_dump(mode="json", exclude_none=False))
        )
        terminals.append(path)
    attestation = {
        "github_run_id": args.github_run_id,
        "github_sha": args.github_sha,
        "artifacts": [
            {
                "name": path.stem,
                "public_digest": sha256_digest(path.read_bytes()),
                "raw_digest": json.loads(path.read_text())["raw_digest"],
            }
            for path in sorted(terminals)
        ],
    }
    attestation_bytes = canonical_json_bytes(attestation)
    expected_provenance = {
        item["name"]: (item["public_digest"], item["raw_digest"])
        for item in attestation["artifacts"]
    }
    artifacts = assemble_public_terminal_release(
        compiled=compiled,
        binding_registry=registry,
        binding_registry_digest=direct_binding_registry_digest(registry_path),
        terminal_paths=tuple(sorted(terminals)),
        release_id=args.release_id,
        version="1.0.0",
        limitations=LIMITATIONS,
        outcome_validator=validate_public_outcome,
        expected_github_run_id=args.github_run_id,
        expected_github_sha=args.github_sha,
        expected_provenance=expected_provenance,
        github_artifacts_manifest_bytes=attestation_bytes,
        binding_registry_bytes=registry_path.read_bytes(),
    )
    artifacts.write(output_dir)
    (output_dir / "github-artifacts.json").write_bytes(attestation_bytes)
    print(release_digest(artifacts.release_bytes))


def _load_summary(
    path: Path, *, expected_count: int
) -> dict[tuple[str, str, int], dict[str, Any]]:
    rows: dict[tuple[str, str, int], dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        item = json.loads(line)
        key = (str(item["provider_id"]), str(item["case_id"]), int(item["round"]))
        if key in rows:
            raise ValueError(f"duplicate probe result: {key}")
        if item.get("state") not in {"passed", "failed"}:
            raise ValueError(f"nonterminal probe result: {key}")
        rows[key] = item
    if len(rows) < expected_count:
        raise ValueError("summary does not contain the expected terminal observations")
    return rows


if __name__ == "__main__":
    main()
