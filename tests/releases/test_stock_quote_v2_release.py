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
RELEASE = ROOT / "releases/stock-quote-2026-q3-v2"
EVIDENCE = ROOT / "evidence/stock-quote-2026-q3-v2"


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
    assert verify_release(RELEASE / "release.json", release_digest(release_bytes))
    assert sha256_digest(run_plan_bytes) == release.run_plan_digest
    assert {cell["run_key"] for cell in json.loads(run_plan_bytes)["cells"]} == {
        cell.run_key for cell in cells
    }
    for bundle in evidence:
        matching = [
            path
            for path in EVIDENCE.glob("*.json")
            if bundle.public_digest == sha256_digest(path.read_bytes())
        ]
        assert matching, bundle.evidence_id
        artifact = json.loads(matching[0].read_text())
        assert artifact["run_key"] == bundle.run_key
        assert artifact["raw_digest"] == bundle.raw_digest
        assert artifact["suite_fingerprint"] == bundle.suite_fingerprint


def _load(name: str) -> list[dict[str, object]]:
    data = json.loads((RELEASE / name).read_text())
    assert isinstance(data, list)
    return data
