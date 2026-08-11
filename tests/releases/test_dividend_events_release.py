from __future__ import annotations

import json
from pathlib import Path

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.replay import replay_release_dir

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "releases/dividend-events-2026-q3-v1"
PUBLIC_EVIDENCE = ROOT / "evidence/dividend-events-2026-q3-v1"
EXPECTED_DIGEST = (
    "sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0"
)


def test_ac9_dividend_release_rebuilds_all_frozen_cells() -> None:
    release = BenchmarkRelease.model_validate_json(
        (RELEASE / "release-input.json").read_text()
    )
    run_plan = RunPlan.model_validate_json((RELEASE / "run-plan.json").read_text())
    cells = tuple(RunCell.model_validate(item) for item in _load("cells.json"))
    evidence = tuple(
        EvidenceBundle.model_validate(item) for item in _load("evidence.json")
    )
    release_bytes = (RELEASE / "release.json").read_bytes()

    assert len(run_plan.cells) == len(cells) == 54
    assert sum(cell.applicable for cell in cells) == len(evidence) == 36
    assert sum(cell.state is CellState.NOT_APPLICABLE for cell in cells) == 18
    assert sum(cell.state is CellState.COMPLETED for cell in cells) == 33
    provider_negatives = [
        cell for cell in cells if cell.state is CellState.PROVIDER_NEGATIVE
    ]
    assert len(provider_negatives) == 3
    assert {cell.provider_id for cell in provider_negatives} == {"ifind"}
    assert {cell.failure_attribution for cell in provider_negatives} == {
        FailureAttribution.EMPTY_OR_PARTIAL_DATA
    }
    assert build_release(release, cells, evidence) == release_bytes
    assert release_digest(release_bytes) == EXPECTED_DIGEST
    assert sha256_digest((RELEASE / "run-plan.json").read_bytes()) == (
        release.run_plan_digest
    )


def test_ac9_public_evidence_binds_every_applicable_cell() -> None:
    cells = {
        item["run_key"]: item for item in _load("cells.json") if item["applicable"]
    }
    evidence = {item["run_key"]: item for item in _load("evidence.json")}
    artifact_paths = {
        artifact["run_key"]: path
        for path in PUBLIC_EVIDENCE.glob("*.json")
        if (artifact := json.loads(path.read_text()))
    }

    assert cells.keys() == evidence.keys()
    assert len(artifact_paths) == 36
    for run_key, path in artifact_paths.items():
        artifact = json.loads(path.read_text())
        bundle = evidence[run_key]
        assert artifact["state"] == cells[run_key]["state"]
        assert artifact["raw_digest"] == bundle["raw_digest"]
        assert sha256_digest(path.read_bytes()) == bundle["public_digest"]
        assert artifact["suite_fingerprint"] == bundle["suite_fingerprint"]
        assert artifact["extractor_version"] == bundle["extractor_version"]


def test_ac9_actions_manifest_and_offline_replay_are_complete() -> None:
    manifest = json.loads((RELEASE / "github-artifacts.json").read_text())

    assert manifest["github_run_id"] == "31473641238"
    assert len(manifest["artifacts"]) == 36
    assert len({item["id"] for item in manifest["artifacts"]}) == 36
    assert all(item["digest"].startswith("sha256:") for item in manifest["artifacts"])
    replay = replay_release_dir(RELEASE, expected_digest=EXPECTED_DIGEST)
    assert replay.expected_digest_verified


def _load(name: str) -> list[dict[str, object]]:
    document = json.loads((RELEASE / name).read_text())
    assert isinstance(document, list)
    return document
