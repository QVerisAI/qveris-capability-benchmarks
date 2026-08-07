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

    assert len(cells) == 24
    assert len(evidence) == 24
    assert {cell.state.value for cell in cells} == {"completed", "provider_negative"}
    assert build_release(release, cells, evidence) == release_bytes
    assert release_digest(release_bytes) == _DIGEST
    assert verify_release(RELEASE / "release.json", _DIGEST)


def test_ac_etf_holdings_public_evidence_matches_frozen_manifest() -> None:
    evidence = json.loads((RELEASE / "evidence.json").read_text())
    files = tuple(EVIDENCE.glob("*.json"))

    assert len(files) == len(evidence) == 24
    public_digests = {sha256_digest(path.read_bytes()) for path in files}
    assert {item["public_digest"] for item in evidence} == public_digests
    assert all(
        item["suite_fingerprint"] == evidence[0]["suite_fingerprint"]
        for item in evidence
    )
