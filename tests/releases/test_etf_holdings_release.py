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
RELEASE = ROOT / "releases/etf-holdings-2026-q3-v1"
EVIDENCE = ROOT / "evidence/etf-holdings-2026-q3-v1"
_DIGEST = "sha256:62df52047ecb0bcf66fce96a0240f97f29c1bc9e55066ca9e06ae0f878d00c0f"


def test_ac_etf_holdings_release_rebuilds_from_all_terminal_evidence() -> None:
    release = BenchmarkRelease.model_validate_json(
        (RELEASE / "release-input.json").read_text()
    )
    cells = tuple(
        RunCell.model_validate(item)
        for item in json.loads((RELEASE / "cells.json").read_text())
    )
    evidence = tuple(
        EvidenceBundle.model_validate(item)
        for item in json.loads((RELEASE / "evidence.json").read_text())
    )
    release_bytes = (RELEASE / "release.json").read_bytes()
    run_plan_bytes = (RELEASE / "run-plan.json").read_bytes()
    run_plan = json.loads(run_plan_bytes)

    assert len(cells) == 24
    assert len(evidence) == 24
    assert {cell.state.value for cell in cells} == {"completed", "provider_negative"}
    assert build_release(release, cells, evidence) == release_bytes
    assert release_digest(release_bytes) == _DIGEST
    assert verify_release(RELEASE / "release.json", _DIGEST)
    assert sha256_digest(run_plan_bytes) == release.run_plan_digest
    assert {item["run_key"] for item in run_plan["cells"]} == {
        cell.run_key for cell in cells
    }

    cells_by_run_key = {cell.run_key: cell for cell in cells}
    expected_binding = {
        ("alpha-vantage", "spy-holdings"): "alpha-vantage-spy-holdings",
        ("alpha-vantage", "qqq-holdings"): "alpha-vantage-qqq-holdings",
        ("alpha-vantage", "iwm-holdings"): "alpha-vantage-iwm-holdings",
        ("alpha-vantage", "invalid-etf"): "alpha-vantage-invalid-etf",
        ("fiu", "spy-holdings"): "fiu-spy-holdings",
        ("fiu", "qqq-holdings"): "fiu-qqq-holdings",
        ("fiu", "iwm-holdings"): "fiu-iwm-holdings",
        ("fiu", "invalid-etf"): "fiu-invalid-etf",
    }
    for bundle in evidence:
        matching = [
            path
            for path in EVIDENCE.glob("*.json")
            if bundle.public_digest == sha256_digest(path.read_bytes())
        ]
        assert len(matching) == 1, bundle.evidence_id
        artifact = json.loads(matching[0].read_text())
        cell = cells_by_run_key[bundle.run_key]
        assert (
            artifact["binding_id"] == expected_binding[(cell.provider_id, cell.case_id)]
        )
        assert artifact["outcome"] == cell.state.value
        assert artifact["run_key"] == bundle.run_key
        assert artifact["raw_digest"] == bundle.raw_digest
        assert artifact["suite_fingerprint"] == bundle.suite_fingerprint
        assert artifact["extractor_version"] == bundle.extractor_version
        assert artifact["redaction_status"] == bundle.redaction_status.value
        assert artifact["disclosure_level"] == bundle.disclosure_level.value
        assert artifact["license_status"] == bundle.license_status.value


def test_ac_etf_holdings_public_evidence_matches_frozen_manifest() -> None:
    evidence = json.loads((RELEASE / "evidence.json").read_text())
    files = tuple(EVIDENCE.glob("*.json"))

    assert len(files) == len(evidence) == 24
    public_digests = {sha256_digest(path.read_bytes()) for path in files}
    assert {item["public_digest"] for item in evidence} == public_digests
