from __future__ import annotations

import json
from pathlib import Path

from qveris_bench.evidence.store import PublicArtifactStore
from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
)
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.suites.compiler import compile_suite
from scripts.build_corporate_actions_v2_release import (
    PACK,
    ROOT,
    build_release_from_artifacts,
)

GITHUB_RUN_ID = "123456"
GITHUB_SHA = "a" * 40


def _terminal_bytes(
    binding, cell, case, fingerprint: str, registry_digest: str
) -> bytes:
    if case.negative_control:
        facts = {"validation_error": "provider_validation_error"}
        attribution = FailureAttribution.PROVIDER_VALIDATION_ERROR
    else:
        identity = binding.request_identity
        assert identity is not None
        facts = {
            "symbol": case.input["symbol"],
            "identity_verified": True,
            "identity_basis": "request_bound",
            "action_type": "split",
            "date": str(case.input["start_date"]),
        }
        attribution = None
    return (
        json.dumps(
            {
                "binding_id": binding.binding_id,
                "run_key": cell.run_key,
                "provider_id": binding.provider_id,
                "access_path_id": binding.access_path_id,
                "transport": binding.transport,
                "state": CellState.COMPLETED,
                "facts": facts,
                "unmet_conditions": [],
                "failure_attribution": attribution,
                "raw_digest": "sha256:" + "b" * 64,
                "binding_registry_digest": registry_digest,
                "extractor_version": "2.0.0",
                "suite_fingerprint": fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
                "latency_ms": 10.0,
                "cost_credits": 2.0,
                "github_run_id": GITHUB_RUN_ID,
                "github_sha": GITHUB_SHA,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


def test_build_release_accepts_digest_suffixed_github_artifacts(
    tmp_path: Path,
) -> None:
    suite_path = PACK / "baseline-suite.yaml"
    cases_path = PACK / "baseline-cases.yaml"
    registry_path = PACK / "baseline-direct-bindings.json"
    compiled = compile_suite(
        suite_path, cases_path, ROOT / "providers", PACK / "cap.yaml"
    )
    registry = load_direct_binding_registry(registry_path)
    bindings = {(item.case_id, item.access_path_id): item for item in registry.bindings}
    cases = {item.case_id: item for item in compiled.cases}
    store = PublicArtifactStore(tmp_path / "downloaded-artifacts")
    for cell in compiled.run_plan.cells:
        if not cell.applicable:
            continue
        binding = bindings[(cell.case_id, cell.access_path_id)]
        store.persist(
            f"{binding.binding_id}-round-{cell.round}",
            _terminal_bytes(
                binding,
                cell,
                cases[cell.case_id],
                compiled.fingerprint,
                direct_binding_registry_digest(registry_path),
            ),
        )

    digest = build_release_from_artifacts(
        store.root,
        tmp_path / "published",
        suite_name="baseline",
        release_id="corporate-actions-v2-test",
        expected_github_run_id=GITHUB_RUN_ID,
        expected_github_sha=GITHUB_SHA,
    )

    assert digest.startswith("sha256:")
    assert (
        tmp_path / "published/releases/corporate-actions-v2-test/release.json"
    ).is_file()
    assert (
        len(
            list(
                (tmp_path / "published/evidence/corporate-actions-v2-test").glob(
                    "*.json"
                )
            )
        )
        == 24
    )
