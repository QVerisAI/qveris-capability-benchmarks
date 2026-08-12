from __future__ import annotations

import json
from pathlib import Path

import pytest

from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
)
from qveris_bench.releases.public_terminal import (
    PublicTerminalReleaseError,
    assemble_public_terminal_release,
)
from qveris_bench.releases.replay import replay_release_dir
from qveris_bench.suites.compiler import compile_suite
from scripts.build_dividend_market_release import LIMITATIONS

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"
PUBLIC_EVIDENCE = ROOT / "evidence/dividend-events-market-coverage-2026-q3-v1"
RELEASE = ROOT / "releases/dividend-events-market-coverage-2026-q3-v1"
EXPECTED_DIGEST = (
    "sha256:7d1d5c0f19e2f1ae7571d57fcc52dbdb24e670317cf3a6f19816df2b1688dde9"
)


def _assemble(paths: tuple[Path, ...] | None = None):
    compiled = compile_suite(
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
    )
    registry_path = PACK / "market-direct-bindings.json"
    return assemble_public_terminal_release(
        compiled=compiled,
        binding_registry=load_direct_binding_registry(registry_path),
        binding_registry_digest=direct_binding_registry_digest(registry_path),
        terminal_paths=paths or tuple(sorted(PUBLIC_EVIDENCE.glob("*.json"))),
        release_id="dividend-events-market-coverage-2026-q3-v1",
        version="1.0.0",
        limitations=LIMITATIONS,
    )


def test_assembles_every_applicable_cell_and_preserves_negative_results() -> None:
    artifacts = _assemble()

    assert len(artifacts.run_plan.cells) == len(artifacts.cells) == 120
    assert len(artifacts.evidence) == 66
    assert sum(cell.applicable for cell in artifacts.cells) == 66
    assert sum(cell.state.value == "not_applicable" for cell in artifacts.cells) == 54
    assert sum(cell.state.value == "completed" for cell in artifacts.cells) == 50
    assert (
        sum(cell.state.value == "provider_negative" for cell in artifacts.cells) == 16
    )
    assert artifacts.release_bytes == artifacts.rebuild()


def test_committed_market_release_exactly_matches_public_terminals() -> None:
    artifacts = _assemble()

    for name, content in artifacts.files().items():
        assert (RELEASE / name).read_bytes() == content
    replay = replay_release_dir(RELEASE, expected_digest=EXPECTED_DIGEST)
    assert replay.expected_digest_verified


def test_rejects_missing_terminal_evidence() -> None:
    paths = tuple(sorted(PUBLIC_EVIDENCE.glob("*.json")))

    with pytest.raises(PublicTerminalReleaseError, match="terminal run keys"):
        _assemble(paths[:-1])


def test_rejects_terminal_identity_drift(tmp_path: Path) -> None:
    paths = list(sorted(PUBLIC_EVIDENCE.glob("*.json")))
    document = json.loads(paths[0].read_text())
    document["provider_id"] = "wrong-provider"
    changed = tmp_path / paths[0].name
    changed.write_text(json.dumps(document), encoding="utf-8")
    paths[0] = changed

    with pytest.raises(PublicTerminalReleaseError, match="cell identity"):
        _assemble(tuple(paths))


def test_rejects_tampered_binding_registry_digest(tmp_path: Path) -> None:
    paths = list(sorted(PUBLIC_EVIDENCE.glob("*.json")))
    document = json.loads(paths[0].read_text())
    document["binding_registry_digest"] = "sha256:" + "f" * 64
    changed = tmp_path / paths[0].name
    changed.write_text(json.dumps(document), encoding="utf-8")
    paths[0] = changed

    with pytest.raises(PublicTerminalReleaseError, match="binding registry digest"):
        _assemble(tuple(paths))
