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
RELEASE = ROOT / "releases/stock-quote-family-2026-q3-v1"
EVIDENCE = ROOT / "evidence/stock-quote-family-2026-q3-v1"
BINDINGS_REGISTRY = ROOT / "cap_packs/qveris-direct-bindings-stock-quote-family.json"
_DIGEST = "sha256:2984a796bee2e9242c818f3336927972fe93030ca13f01f459e7333d5d509f57"

_EXPECTED_BINDING = {
    ("finnhub", "aapl-quote"): "finnhub-aapl-quote-family",
    ("finnhub", "invalid-stock"): "finnhub-invalid-stock-family",
    ("finnhub", "aapl-freshness-precision"): "finnhub-aapl-freshness-family",
    ("finnhub", "cn-600519-market-coverage"): "finnhub-600519-coverage-family",
    ("finnhub", "cn-600519-agent-contract"): "finnhub-600519-agent-family",
    ("eodhd", "aapl-quote"): "eodhd-aapl-quote-family",
    ("eodhd", "invalid-stock"): "eodhd-invalid-stock-family",
    ("eodhd", "aapl-freshness-precision"): "eodhd-aapl-freshness-family",
    ("eodhd", "cn-600519-market-coverage"): "eodhd-600519-coverage-family",
    ("eodhd", "cn-600519-agent-contract"): "eodhd-600519-agent-family",
}


def _binding_digest(binding: QverisDirectBinding) -> str:
    return sha256_digest(
        json.dumps(
            binding.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    )


def test_ac_stock_quote_family_release_rebuilds_all_direct_terminal_evidence() -> None:
    release = BenchmarkRelease.model_validate_json(
        (RELEASE / "release-input.json").read_text()
    )
    cells = tuple(RunCell.model_validate(item) for item in _load("cells.json"))
    evidence = tuple(
        EvidenceBundle.model_validate(item) for item in _load("evidence.json")
    )
    release_bytes = (RELEASE / "release.json").read_bytes()
    run_plan_bytes = (RELEASE / "run-plan.json").read_bytes()

    assert len(cells) == 30
    assert {cell.state.value for cell in cells} == {"completed", "provider_negative"}
    assert sum(cell.state is CellState.COMPLETED for cell in cells) == 6
    assert len(evidence) == 30
    assert build_release(release, cells, evidence) == release_bytes
    assert release_digest(release_bytes) == _DIGEST
    assert verify_release(RELEASE / "release.json", _DIGEST)
    assert sha256_digest(run_plan_bytes) == release.run_plan_digest
    assert {cell["run_key"] for cell in json.loads(run_plan_bytes)["cells"]} == {
        cell.run_key for cell in cells
    }

    cells_by_run_key = {cell.run_key: cell for cell in cells}
    registry_digest = sha256_digest(BINDINGS_REGISTRY.read_bytes())
    for bundle in evidence:
        matching = [
            path
            for path in EVIDENCE.glob("*.json")
            if bundle.public_digest == sha256_digest(path.read_bytes())
        ]
        assert len(matching) == 1, bundle.evidence_id
        artifact = json.loads(matching[0].read_text())
        cell = cells_by_run_key[bundle.run_key]
        expected_binding = _EXPECTED_BINDING[(cell.provider_id, cell.case_id)]
        assert artifact["binding_id"] == expected_binding
        assert artifact["outcome"] == cell.state.value
        if cell.state is CellState.COMPLETED:
            assert artifact["reason"] is None
        else:
            assert artifact["reason"] in {
                "stale_timestamp",
                "invalid_timestamp",
                "unavailable_quote",
            }
        assert artifact["run_key"] == bundle.run_key
        assert artifact["raw_digest"] == bundle.raw_digest
        assert artifact["suite_fingerprint"] == bundle.suite_fingerprint
        assert artifact["extractor_version"] == bundle.extractor_version
        assert artifact["redaction_status"] == bundle.redaction_status.value
        assert artifact["disclosure_level"] == bundle.disclosure_level.value
        assert artifact["license_status"] == bundle.license_status.value
        binding = load_registered_qveris_direct_binding(
            BINDINGS_REGISTRY, artifact["binding_id"]
        )
        assert artifact["binding_digest"] == _binding_digest(binding)
        assert artifact["binding_registry_digest"] == registry_digest
        assert artifact["github_run_id"]
        assert artifact["github_sha"]


def test_ac_stock_quote_family_release_has_complete_actions_artifact_manifest() -> None:
    manifest = json.loads((RELEASE / "github-artifacts.json").read_text())

    assert manifest["github_run_id"] == "31181603165"
    assert manifest["github_sha"] == "b25422caacce681750d5304682a95d9bdc3e8906"
    assert len(manifest["artifacts"]) == 30
    assert len({item["id"] for item in manifest["artifacts"]}) == 30
    assert all(item["digest"].startswith("sha256:") for item in manifest["artifacts"])


def _load(name: str) -> list[dict[str, object]]:
    data = json.loads((RELEASE / name).read_text())
    assert isinstance(data, list)
    return data
