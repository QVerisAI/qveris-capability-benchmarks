import json
from pathlib import Path

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.verify import verify_release

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "releases/stock-quote-smoke-2026-q3-v1"
EVIDENCE = ROOT / "evidence/stock-quote-smoke-2026-q3-v1"
_DIGEST = "sha256:f0535988872ec0b300de726a1ec3e6c28988ba39401ea6bdb04d8a739798f2b3"


def test_ac_stock_quote_smoke_release_rebuilds_from_safe_evidence() -> None:
    release = BenchmarkRelease.model_validate_json(
        (RELEASE / "release-input.json").read_text()
    )
    cells = tuple(RunCell.model_validate(item) for item in _load("cells.json"))
    evidence = tuple(
        EvidenceBundle.model_validate(item) for item in _load("evidence.json")
    )

    release_bytes = (RELEASE / "release.json").read_bytes()
    run_plan_bytes = (RELEASE / "run-plan.json").read_bytes()
    run_plan = json.loads(run_plan_bytes)
    # 历史 release 早于归因门禁，replay 重建跳过发布期归因校验
    assert (
        build_release(release, cells, evidence, require_attribution=False)
        == release_bytes
    )
    assert release_digest(release_bytes) == _DIGEST
    assert verify_release(RELEASE / "release.json", _DIGEST)
    assert sha256_digest(run_plan_bytes) == release.run_plan_digest
    assert {cell["run_key"] for cell in run_plan["cells"]} == {
        cell.run_key for cell in cells
    }
    expected_terminal = {
        cells[0].run_key: ("finnhub-aapl-quote", "provider_negative"),
        cells[1].run_key: ("finnhub-invalid-stock", "completed"),
    }
    for bundle in evidence:
        matching = [
            path
            for path in EVIDENCE.glob("*.json")
            if bundle.public_digest == sha256_digest(path.read_bytes())
        ]
        assert matching, bundle.evidence_id
        artifact = json.loads(matching[0].read_text())
        binding_id, outcome = expected_terminal[bundle.run_key]
        assert artifact["binding_id"] == binding_id
        assert artifact["outcome"] == outcome
        assert artifact["raw_digest"] == bundle.raw_digest
        assert artifact["suite_fingerprint"] == bundle.suite_fingerprint
        assert artifact["extractor_version"] == bundle.extractor_version
        assert artifact["redaction_status"] == bundle.redaction_status.value
        assert artifact["disclosure_level"] == bundle.disclosure_level.value
        assert artifact["license_status"] == bundle.license_status.value


def _load(name: str) -> list[dict[str, object]]:
    data = json.loads((RELEASE / name).read_text())
    assert isinstance(data, list)
    return data
