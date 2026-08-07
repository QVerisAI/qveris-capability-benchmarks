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
RELEASE = ROOT / "releases/stock-quote-2026-q3-v2"
EVIDENCE = ROOT / "evidence/stock-quote-2026-q3-v2"
_DIGEST = "sha256:7e7ff0ebf2c72e96e6bb1544c07da4195f82154378b686d544667b922d5a6e4b"


def _binding_digest(binding: QverisDirectBinding) -> str:
    return sha256_digest(
        json.dumps(
            binding.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    )


def test_ac_stock_quote_v2_release_rebuilds_all_direct_terminal_evidence() -> None:
    release = BenchmarkRelease.model_validate_json(
        (RELEASE / "release-input.json").read_text()
    )
    cells = tuple(RunCell.model_validate(item) for item in _load("cells.json"))
    evidence = tuple(
        EvidenceBundle.model_validate(item) for item in _load("evidence.json")
    )
    release_bytes = (RELEASE / "release.json").read_bytes()
    run_plan_bytes = (RELEASE / "run-plan.json").read_bytes()

    assert len(cells) == 8
    assert {cell.state.value for cell in cells} == {"completed", "provider_negative"}
    assert len(evidence) == 8
    assert build_release(release, cells, evidence) == release_bytes
    assert release_digest(release_bytes) == _DIGEST
    assert verify_release(RELEASE / "release.json", _DIGEST)
    assert sha256_digest(run_plan_bytes) == release.run_plan_digest
    assert {cell["run_key"] for cell in json.loads(run_plan_bytes)["cells"]} == {
        cell.run_key for cell in cells
    }
    cells_by_run_key = {cell.run_key: cell for cell in cells}
    expected_binding = {
        ("finnhub", "aapl-quote"): "finnhub-aapl-quote-v2",
        ("finnhub", "invalid-stock"): "finnhub-invalid-stock-v2",
        ("eodhd", "aapl-quote"): "eodhd-aapl-quote",
        ("eodhd", "invalid-stock"): "eodhd-invalid-stock",
    }
    bindings_path = ROOT / "cap_packs/qveris-direct-bindings.json"
    registry_digest = sha256_digest(bindings_path.read_bytes())
    for bundle in evidence:
        matching = [
            path
            for path in EVIDENCE.glob("*.json")
            if bundle.public_digest == sha256_digest(path.read_bytes())
        ]
        assert len(matching) == 1, bundle.evidence_id
        artifact = json.loads(matching[0].read_text())
        cell = cells_by_run_key[bundle.run_key]
        assert artifact["binding_id"] == expected_binding[
            (cell.provider_id, cell.case_id)
        ]
        assert artifact["outcome"] == cell.state.value
        if cell.state is CellState.COMPLETED:
            assert artifact["reason"] is None
        else:
            assert artifact["reason"] in {"stale_timestamp", "invalid_timestamp"}
        assert artifact["run_key"] == bundle.run_key
        assert artifact["raw_digest"] == bundle.raw_digest
        assert artifact["suite_fingerprint"] == bundle.suite_fingerprint
        assert artifact["extractor_version"] == bundle.extractor_version
        assert artifact["redaction_status"] == bundle.redaction_status.value
        assert artifact["disclosure_level"] == bundle.disclosure_level.value
        assert artifact["license_status"] == bundle.license_status.value
        binding = load_registered_qveris_direct_binding(
            bindings_path, artifact["binding_id"]
        )
        assert artifact["binding_digest"] == _binding_digest(binding)
        assert artifact["binding_registry_digest"] == registry_digest
        assert artifact["github_run_id"]
        assert artifact["github_sha"]


def _load(name: str) -> list[dict[str, object]]:
    data = json.loads((RELEASE / name).read_text())
    assert isinstance(data, list)
    return data
