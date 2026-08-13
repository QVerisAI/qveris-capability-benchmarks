from __future__ import annotations

import json
from pathlib import Path

from qveris_bench.cap_packs.dividend_events.direct import (
    validate_public_dividend_outcome,
)
from qveris_bench.cap_packs.dividend_events.models import (
    validate_dividend_request_identities,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.public_terminal import assemble_public_terminal_release
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs/dividend_events"
RELEASE_ID = "dividend-events-market-coverage-2026-q3-v1"
PUBLIC_EVIDENCE = ROOT / "evidence" / RELEASE_ID
OUTPUT = ROOT / "releases" / RELEASE_ID
LIMITATIONS = (
    "Coverage is measured per Provider and Access Path using one fixed "
    "representative symbol per market over 2024-01-01 through 2026-07-31; "
    "it is not a provider-wide market guarantee.",
    "Each applicable Direct cell ran twice. A market is supported only when "
    "both rounds completed with the required dividend-event fields and "
    "verified request identity.",
    "Explicitly unsupported QVeris markets and markets outside an Access "
    "Path contract are not called again; they remain not_applicable with "
    "the frozen reason in the run plan.",
    "Offline replay verifies the published artifacts and release bytes. It "
    "does not call providers or prove their current behavior.",
)


def main() -> None:
    registry_path = PACK / "market-direct-bindings.json"
    compiled = compile_suite(
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
    )
    registry = load_direct_binding_registry(registry_path)
    validate_direct_binding_registry(
        registry,
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        cap_path=PACK / "cap.yaml",
    )
    validate_dividend_request_identities(registry, compiled)
    attestation_path = OUTPUT / "github-artifacts.json"
    attestation_bytes = attestation_path.read_bytes()
    attestation = json.loads(attestation_bytes)
    expected_artifacts = {
        path.stem: (
            sha256_digest(path.read_bytes()),
            json.loads(path.read_text())["raw_digest"],
        )
        for path in PUBLIC_EVIDENCE.glob("*.json")
    }
    observed_artifacts = {
        item["name"].removeprefix("dividend-market-"): (
            item["public_digest"],
            item["raw_digest"],
        )
        for item in attestation["artifacts"]
    }
    if observed_artifacts != expected_artifacts:
        raise ValueError("GitHub artifact attestation does not match public evidence")
    artifacts = assemble_public_terminal_release(
        compiled=compiled,
        binding_registry=registry,
        binding_registry_digest=direct_binding_registry_digest(registry_path),
        terminal_paths=tuple(sorted(PUBLIC_EVIDENCE.glob("*.json"))),
        release_id=RELEASE_ID,
        version="1.0.0",
        limitations=LIMITATIONS,
        outcome_validator=lambda case, binding, facts: validate_public_dividend_outcome(
            case, binding, facts, PACK / "observation-schema.yaml"
        ),
        expected_github_run_id=attestation["github_run_id"],
        expected_github_sha=attestation["github_sha"],
        expected_provenance=observed_artifacts,
        github_artifacts_manifest_bytes=attestation_bytes,
    )
    artifacts.write(OUTPUT)
    print(release_digest(artifacts.release_bytes))


if __name__ == "__main__":
    main()
