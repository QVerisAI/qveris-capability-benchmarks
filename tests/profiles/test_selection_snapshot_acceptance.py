from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from qveris_bench.models.selection import (
    GatewayMetricsSnapshot,
    OfficialPricingSnapshot,
    RunObservationsSnapshot,
)
from qveris_bench.profiles.selection import (
    SelectionSnapshotBuildError,
    _agent_interface,
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


def test_ac3_snapshot_consumes_released_market_results() -> None:
    rows = {
        row.access_path_id: row
        for row in build_selection_snapshot(INPUT, ROOT).snapshot.rows
    }

    eodhd = {
        result.market: result.state
        for result in rows["eodhd-dividends-qveris"].market_coverage.results
    }
    assert {market for market, state in eodhd.items() if state == "verified"} == {
        "US",
        "HK",
        "CN",
        "DE",
        "FR",
        "BR",
        "ES",
    }
    assert {
        market for market, state in eodhd.items() if state == "provider_negative"
    } == {
        "JP",
        "IN",
    }
    alpha = {
        result.market: result.state
        for result in rows["alpha-vantage-dividends-qveris"].market_coverage.results
    }
    assert sum(state == "verified" for state in alpha.values()) == 4
    assert sum(state == "not_applicable" for state in alpha.values()) == 5
    native = rows["ifind-native-mcp"].market_coverage
    assert {
        result.market
        for result in native.results
        if result.state == "provider_negative"
    } == {"US", "HK", "CN"}
    assert all(
        row.market_coverage.release_digest
        == build_selection_snapshot(INPUT, ROOT).snapshot.market_coverage_release_digest
        for row in rows.values()
    )


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


def test_ac5_qveris_list_prices_come_from_inspect_not_account_billing() -> None:
    rows = {
        row.access_path_id: row
        for row in build_selection_snapshot(INPUT, ROOT).snapshot.rows
    }
    expected = {
        "hangseng-dividends-qveris": 1.0,
        "massive-stocks-dividends-qveris": 1.0,
        "alpha-vantage-dividends-qveris": 0.0,
        "twelve-data-dividends-qveris": 2.37,
        "eodhd-dividends-qveris": 2.81,
    }

    for access_path_id, amount in expected.items():
        price = rows[access_path_id].qveris_list_price
        assert price.state == "declared"
        assert price.amount_credits == amount
        assert price.unit == "per_call"
        assert price.source == "qveris_inspect"
        assert price.snapshot_version == "website-default"
        assert price.evidence_ref.startswith("sha256:")

    native = rows["ifind-native-mcp"].qveris_list_price
    assert native.state == "not_applicable"
    assert native.amount_credits is None


@pytest.mark.parametrize("mutation", ["string_amount", "wrong_tool", "wrong_digest"])
def test_ac5_qveris_list_pricing_fails_closed(tmp_path: Path, mutation: str) -> None:
    pricing = json.loads(
        (INPUT.parent / "qveris-list-pricing.json").read_text(encoding="utf-8")
    )
    if mutation == "string_amount":
        pricing["prices"][0]["amount_credits"] = "1"
    elif mutation == "wrong_tool":
        pricing["prices"][0]["tool_id"] = pricing["prices"][1]["tool_id"]
    else:
        pricing["bindings_digest"] = f"sha256:{'f' * 64}"
    pricing_path = tmp_path / "qveris-list-pricing.json"
    pricing_path.write_text(json.dumps(pricing), encoding="utf-8")
    config = yaml.safe_load(INPUT.read_text(encoding="utf-8"))
    config["qveris_list_pricing"]["snapshot"] = str(pricing_path)
    input_path = tmp_path / "selection-snapshot.yaml"
    input_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(SelectionSnapshotBuildError):
        build_selection_snapshot(input_path, ROOT)


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


def test_ac6_provider_negative_is_not_an_agent_signal_pass() -> None:
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
    evidence_by_run_key = {item["run_key"]: item for item in release["evidence"]}
    result = _agent_interface(
        negatives,
        {"invalid-dividend-symbol": True},
        evidence_by_run_key,
    )
    assert result.invalid_input_handling.passed == 1
    assert result.invalid_input_handling.total == 3


def test_ac1_snapshot_rejects_release_digest_drift(tmp_path: Path) -> None:
    input_path = tmp_path / "selection.yaml"
    text = INPUT.read_text(encoding="utf-8").replace(
        "sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0",
        "sha256:" + "0" * 64,
    )
    input_path.write_text(text, encoding="utf-8")

    with pytest.raises(SelectionSnapshotBuildError, match="release digest mismatch"):
        build_selection_snapshot(input_path, ROOT)


def test_ac3_snapshot_rejects_market_release_digest_drift(tmp_path: Path) -> None:
    input_path = tmp_path / "selection.yaml"
    text = INPUT.read_text(encoding="utf-8").replace(
        "sha256:52f432c581fc6e8868e9070be21ad1b210b59238fb4c26d252f2a13a2d93f70e",
        "sha256:" + "0" * 64,
    )
    input_path.write_text(text, encoding="utf-8")

    with pytest.raises(
        SelectionSnapshotBuildError,
        match="market coverage release digest mismatch",
    ):
        build_selection_snapshot(input_path, ROOT)


def test_ac1_snapshot_rejects_release_identity_tampering(tmp_path: Path) -> None:
    release_dir = tmp_path / "dividend-events-2026-q3-v1"
    shutil.copytree(ROOT / "releases/dividend-events-2026-q3-v1", release_dir)
    release_path = release_dir / "release.json"
    release = json.loads(release_path.read_text())
    cell = next(cell for cell in release["cells"] if cell["applicable"])
    cell["provider_id"] = "twelve-data"
    release_path.write_text(json.dumps(release), encoding="utf-8")
    input_path = _selection_input_for_release(tmp_path, release_path)

    with pytest.raises(SelectionSnapshotBuildError, match="run key|release replay"):
        build_selection_snapshot(input_path, ROOT)


def test_ac1_snapshot_rejects_case_semantic_drift(tmp_path: Path) -> None:
    cases = tmp_path / "cases.yaml"
    source = (ROOT / "cap_packs/dividend_events/cases.yaml").read_text()
    cases.write_text(
        source.replace(
            "Return AAPL dividend events within a fixed window",
            "Return AAPL dividend events using changed semantics",
        ),
        encoding="utf-8",
    )
    input_path = tmp_path / "selection.yaml"
    input_path.write_text(
        INPUT.read_text().replace("cap_packs/dividend_events/cases.yaml", str(cases)),
        encoding="utf-8",
    )

    with pytest.raises(SelectionSnapshotBuildError, match="fingerprint mismatch"):
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


def test_selection_models_reject_contradictory_states() -> None:
    evidence_ref = "sha256:" + "a" * 64
    with pytest.raises(ValidationError, match="out of order"):
        GatewayMetricsSnapshot(
            state="measured",
            latency_sample_size=1,
            latency_min_ms=3,
            latency_median_ms=2,
            latency_max_ms=1,
            cost_sample_size=0,
            evidence_refs=(evidence_ref,),
            latency_evidence_refs=(evidence_ref,),
        )
    with pytest.raises(ValidationError, match="unmeasured run observations"):
        RunObservationsSnapshot(
            state="evidence_insufficient",
            terminal_observations=1,
            planned_observations=1,
            evidence_refs=(evidence_ref,),
        )
    with pytest.raises(ValidationError, match="cannot carry declarations"):
        OfficialPricingSnapshot(
            state="evidence_insufficient",
            currencies=("USD",),
        )


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
