from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from qveris_bench.profiles.selection import (
    SelectionSnapshotBuildError,
    build_selection_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.yaml"


def test_ac1_snapshot_is_deterministic_scoped_and_digest_bound() -> None:
    first = build_selection_snapshot(INPUT, ROOT)
    second = build_selection_snapshot(INPUT, ROOT)

    assert first.json_bytes == second.json_bytes
    assert first.json_bytes == INPUT.with_suffix(".json").read_bytes()
    document = json.loads(first.json_bytes)
    assert document["cap_release_digest"].startswith("sha256:")
    assert document["input_digests"]["cases"].startswith("sha256:")
    assert len(document["rows"]) == 6
    for row in document["rows"]:
        assert row["provider_id"]
        assert row["access_path_id"]
        assert row["cap_id"] == "dividend-events"
        assert row["observation_window"] == {
            "start": "2026-08-11",
            "end": "2026-08-11",
        }


def test_ac3_snapshot_separates_tested_markets_from_verified_sv() -> None:
    rows = {
        row.access_path_id: row
        for row in build_selection_snapshot(INPUT, ROOT).snapshot.rows
    }

    assert rows["ifind-native-mcp"].market_coverage.tested_markets == ("CN",)
    assert rows["twelve-data-dividends-qveris"].market_coverage.tested_markets == (
        "US",
    )
    for access_path_id, row in rows.items():
        if access_path_id == "ifind-native-mcp":
            assert row.market_coverage.sv_state == "not_applicable"
        else:
            assert row.market_coverage.sv_state == "evidence_insufficient"
            assert row.market_coverage.sv_verified_markets == ()


def test_ac4_gateway_metrics_never_leak_into_native_path() -> None:
    rows = {
        row.access_path_id: row
        for row in build_selection_snapshot(INPUT, ROOT).snapshot.rows
    }

    native = rows["ifind-native-mcp"].gateway_metrics
    assert native.state == "not_applicable"
    assert native.measurement_boundary == "qveris_gateway"
    assert native.latency_sample_size == 0
    qveris_rows = [row for path, row in rows.items() if path != "ifind-native-mcp"]
    assert len(qveris_rows) == 5
    for row in qveris_rows:
        assert row.gateway_metrics.state == "measured"
        assert row.gateway_metrics.latency_sample_size == 6
        assert row.gateway_metrics.cost_sample_size == 3
        assert row.gateway_metrics.evidence_refs
    for row in rows.values():
        assert row.run_observations.state == "measured"
        assert row.run_observations.terminal_observations == 6
        assert row.run_observations.planned_observations == 6
        assert row.run_observations.evidence_refs


def test_ac5_pricing_respects_access_path_scope() -> None:
    rows = {
        row.access_path_id: row
        for row in build_selection_snapshot(INPUT, ROOT).snapshot.rows
    }

    assert rows["ifind-native-mcp"].official_pricing.state == "declared"
    assert "CNY 40/month" in rows["ifind-native-mcp"].official_pricing.paid_plans
    assert rows["alpha-vantage-dividends-qveris"].official_pricing.state == ("declared")
    assert rows["massive-stocks-dividends-qveris"].official_pricing.state == (
        "evidence_insufficient"
    )
    alpha = rows["alpha-vantage-dividends-qveris"].official_pricing
    assert alpha.applies_to == "provider_wide"
    assert alpha.extractor_version == "1.0.0"
    assert alpha.suite_fingerprint
    assert alpha.disclosure_level == "sanitized_public"
    assert alpha.license_status == "cleared"


def test_ac6_agent_signals_remain_independent_dimensions() -> None:
    rows = build_selection_snapshot(INPUT, ROOT).snapshot.rows

    for row in rows:
        signals = row.agent_interface.model_dump(mode="json")
        assert signals["invalid_input_handling"]["state"] == "measured"
        assert signals["invalid_input_handling"]["passed"] == 3
        assert signals["invalid_input_handling"]["total"] == 3
        for name in (
            "parameter_clarity",
            "schema_stability",
            "pagination",
            "single_tool_completion",
        ):
            assert signals[name]["state"] == "evidence_insufficient"
        assert all(
            token not in json.dumps(signals).lower()
            for token in ("score", "rating", "agent_friendly")
        )


def test_ac6_provider_negative_is_not_an_agent_signal_pass(tmp_path: Path) -> None:
    release = json.loads(
        (ROOT / "releases/dividend-events-2026-q3-v1/release.json").read_text()
    )
    negatives = [
        cell
        for cell in release["cells"]
        if cell["provider_id"] == "twelve-data"
        and cell["case_id"] == "invalid-dividend-symbol"
    ]
    for cell in negatives[1:]:
        cell["state"] = "provider_negative"
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release), encoding="utf-8")
    input_path = _selection_input_for_release(tmp_path, release_path)

    row = next(
        row
        for row in build_selection_snapshot(input_path, ROOT).snapshot.rows
        if row.provider_id == "twelve-data"
    )
    assert row.agent_interface.invalid_input_handling.passed == 1
    assert row.agent_interface.invalid_input_handling.total == 3


def test_ac1_snapshot_rejects_release_digest_drift(tmp_path: Path) -> None:
    input_path = tmp_path / "selection.yaml"
    text = INPUT.read_text(encoding="utf-8").replace(
        "sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0",
        "sha256:" + "0" * 64,
    )
    input_path.write_text(text, encoding="utf-8")

    with pytest.raises(SelectionSnapshotBuildError, match="release digest mismatch"):
        build_selection_snapshot(input_path, ROOT)


def test_ac3_snapshot_consumes_only_identity_matched_sv_results(
    tmp_path: Path,
) -> None:
    sv_path = tmp_path / "sv.json"
    sv_document = {
        "snapshot_id": "dividend-sv-2026-q3-v1",
        "version": "1.0.0",
        "namespace": "MKT.DIVIDENDS",
        "observation_window": {"start": "2026-08-11", "end": "2026-08-11"},
        "suite_fingerprint": "b" * 64,
        "extractor_version": "1.0.0",
        "disclosure_level": "sanitized_public",
        "license_status": "cleared",
        "results": [
            {
                "provider_id": "twelve-data",
                "access_path_id": "twelve-data-dividends-qveris",
                "market": "US",
                "supported": True,
                "evidence_ref": "sha256:" + "a" * 64,
            }
        ],
    }
    sv_path.write_text(json.dumps(sv_document), encoding="utf-8")
    sv_digest = _digest(sv_path)
    input_path = tmp_path / "selection.yaml"
    input_path.write_text(
        INPUT.read_text(encoding="utf-8").replace(
            "snapshot: null\n  snapshot_digest: null",
            f"snapshot: {sv_path}\n  snapshot_digest: {sv_digest}",
        ),
        encoding="utf-8",
    )

    rows = {
        row.access_path_id: row
        for row in build_selection_snapshot(input_path, ROOT).snapshot.rows
    }
    coverage = rows["twelve-data-dividends-qveris"].market_coverage
    assert coverage.sv_state == "measured"
    assert coverage.sv_verified_markets == ("US",)
    assert coverage.sv_evidence_refs == ("sha256:" + "a" * 64,)

    sv_path.write_text(
        sv_path.read_text(encoding="utf-8").replace(
            "twelve-data-dividends-qveris", "twelve-data-unknown"
        ),
        encoding="utf-8",
    )
    input_path.write_text(
        input_path.read_text().replace(sv_digest, _digest(sv_path)),
        encoding="utf-8",
    )
    with pytest.raises(SelectionSnapshotBuildError, match="unknown SV identity"):
        build_selection_snapshot(input_path, ROOT)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("supported", "false"), "valid boolean"),
        (
            ("observation_window", {"start": "2026-08-10", "end": "2026-08-10"}),
            "window mismatch",
        ),
        (("disclosure_level", "private"), "publishable provenance"),
    ],
)
def test_ac3_snapshot_rejects_untrusted_sv(
    tmp_path: Path, mutation: tuple[str, object], message: str
) -> None:
    document = {
        "snapshot_id": "dividend-sv-2026-q3-v1",
        "version": "1.0.0",
        "namespace": "MKT.DIVIDENDS",
        "observation_window": {"start": "2026-08-11", "end": "2026-08-11"},
        "suite_fingerprint": "b" * 64,
        "extractor_version": "1.0.0",
        "disclosure_level": "sanitized_public",
        "license_status": "cleared",
        "results": [
            {
                "provider_id": "twelve-data",
                "access_path_id": "twelve-data-dividends-qveris",
                "market": "US",
                "supported": True,
                "evidence_ref": "sha256:" + "a" * 64,
            }
        ],
    }
    key, value = mutation
    if key == "supported":
        document["results"][0][key] = value
    else:
        document[key] = value
    sv_path = tmp_path / "sv.json"
    sv_path.write_text(json.dumps(document), encoding="utf-8")
    input_path = tmp_path / "selection.yaml"
    input_path.write_text(
        INPUT.read_text().replace(
            "snapshot: null\n  snapshot_digest: null",
            f"snapshot: {sv_path}\n  snapshot_digest: {_digest(sv_path)}",
        ),
        encoding="utf-8",
    )

    with pytest.raises(SelectionSnapshotBuildError, match=message):
        build_selection_snapshot(input_path, ROOT)


def test_ac1_snapshot_rejects_release_identity_tampering(tmp_path: Path) -> None:
    release = json.loads(
        (ROOT / "releases/dividend-events-2026-q3-v1/release.json").read_text()
    )
    cell = next(cell for cell in release["cells"] if cell["applicable"])
    cell["provider_id"] = "twelve-data"
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release), encoding="utf-8")
    input_path = _selection_input_for_release(tmp_path, release_path)

    with pytest.raises(SelectionSnapshotBuildError, match="run key"):
        build_selection_snapshot(input_path, ROOT)


def test_ac8_snapshot_build_runs_through_installed_cli(tmp_path: Path) -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None
    output = tmp_path / "selection-snapshot.json"

    result = subprocess.run(
        [
            executable,
            "selection",
            "build",
            "--input",
            str(INPUT),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["rows"]


def _digest(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _selection_input_for_release(tmp_path: Path, release_path: Path) -> Path:
    input_path = tmp_path / "selection.yaml"
    source = INPUT.read_text(encoding="utf-8")
    old_path = "releases/dividend-events-2026-q3-v1/release.json"
    old_digest = (
        "sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0"
    )
    input_path.write_text(
        source.replace(old_path, str(release_path)).replace(
            old_digest, _digest(release_path)
        ),
        encoding="utf-8",
    )
    return input_path
