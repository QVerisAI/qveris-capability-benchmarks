from __future__ import annotations

import json
from pathlib import Path

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.qveris_binding import (
    QverisDirectBinding,
    load_registered_qveris_direct_binding,
)
from qveris_bench.models.enums import CellState
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.verify import verify_release

ROOT = Path(__file__).resolve().parents[2]
_FSF_DIGEST = "sha256:a22d3dbcb47d094baac201a0c100e6ad87b6159d6780bdf29ea3c5f0e4a8abaf"
_SEC_DIGEST = "sha256:5a159d6e5777b3829e57f861e18182a76540d94dc1f3b8c23ae4410207e5024e"

RELEASES = {
    "financial-statements-2026-q3-v1": {
        "registry": ROOT / "cap_packs/qveris-direct-bindings-financial-statements.json",
        "digest": _FSF_DIGEST,
        "run": "31196948617",
        "sha": "8b7fe9fa610a5a5a6e358e0968fb6fdecd9d54b8",
        "reasons": {"invalid_revenue"},
        "states": {"completed", "provider_negative"},
    },
    "sec-filing-evidence-2026-q3-v1": {
        "registry": ROOT / "cap_packs/qveris-direct-bindings-sec-filing-evidence.json",
        "digest": _SEC_DIGEST,
        "run": "31193812794",
        "sha": "f3bbbed47eb0b4fa4b841ffc1b64a859e5dd5297",
        "reasons": {"unexpected_response_shape"},
        "states": {"provider_negative"},
    },
}


def _binding_digest(binding: QverisDirectBinding) -> str:
    return sha256_digest(
        json.dumps(
            binding.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    )


def test_ac_fsf_sec_releases_rebuild_all_direct_terminal_evidence() -> None:
    for release_id, meta in RELEASES.items():
        release_dir = ROOT / f"releases/{release_id}"
        evidence_dir = ROOT / f"evidence/{release_id}"
        release = BenchmarkRelease.model_validate_json(
            (release_dir / "release-input.json").read_text()
        )
        cells = tuple(
            RunCell.model_validate(item) for item in _load(release_dir, "cells.json")
        )
        evidence = tuple(
            EvidenceBundle.model_validate(item)
            for item in _load(release_dir, "evidence.json")
        )
        release_bytes = (release_dir / "release.json").read_bytes()
        run_plan_bytes = (release_dir / "run-plan.json").read_bytes()

        assert len(cells) == 6, release_id
        assert {cell.state.value for cell in cells} == meta["states"]
        assert len(evidence) == 6
        assert build_release(release, cells, evidence) == release_bytes
        assert release_digest(release_bytes) == meta["digest"]
        assert verify_release(release_dir / "release.json", meta["digest"])
        assert sha256_digest(run_plan_bytes) == release.run_plan_digest
        assert {cell["run_key"] for cell in json.loads(run_plan_bytes)["cells"]} == {
            cell.run_key for cell in cells
        }

        cells_by_run_key = {cell.run_key: cell for cell in cells}
        registry_digest = sha256_digest(meta["registry"].read_bytes())
        for bundle in evidence:
            matching = [
                path
                for path in evidence_dir.glob("*.json")
                if bundle.public_digest == sha256_digest(path.read_bytes())
            ]
            assert len(matching) == 1, bundle.evidence_id
            artifact = json.loads(matching[0].read_text())
            cell = cells_by_run_key[bundle.run_key]
            assert artifact["outcome"] == cell.state.value
            if cell.state is CellState.COMPLETED:
                assert artifact["reason"] is None
            else:
                assert artifact["reason"] in meta["reasons"]
            assert artifact["run_key"] == bundle.run_key
            assert artifact["raw_digest"] == bundle.raw_digest
            assert artifact["suite_fingerprint"] == bundle.suite_fingerprint
            binding = load_registered_qveris_direct_binding(
                meta["registry"], artifact["binding_id"]
            )
            assert artifact["binding_digest"] == _binding_digest(binding)
            assert artifact["binding_registry_digest"] == registry_digest
            assert artifact["github_run_id"] == meta["run"]
            assert artifact["github_sha"] == meta["sha"]


def test_ac_fsf_sec_releases_have_complete_actions_artifact_manifests() -> None:
    for release_id, meta in RELEASES.items():
        manifest = json.loads(
            (ROOT / f"releases/{release_id}/github-artifacts.json").read_text()
        )

        assert manifest["github_run_id"] == meta["run"]
        assert manifest["github_sha"] == meta["sha"]
        assert len(manifest["artifacts"]) == 6
        assert len({item["id"] for item in manifest["artifacts"]}) == 6
        assert all(
            item["digest"].startswith("sha256:") for item in manifest["artifacts"]
        )


def _load(release_dir: Path, name: str) -> list[dict[str, object]]:
    data = json.loads((release_dir / name).read_text())
    assert isinstance(data, list)
    return data
