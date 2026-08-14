from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from qveris_bench.profiles.selection import build_selection_snapshot

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "selection_snapshots/corporate-actions-v2/selection-snapshot.yaml"
SNAPSHOT = INPUT.with_suffix(".json")
MARKETS = {"US", "HK", "CN", "JP", "DE", "FR", "BR", "IN", "ES"}


def test_ac1_corporate_v2_snapshot_rebuilds_exactly_from_releases() -> None:
    build = build_selection_snapshot(INPUT, ROOT)

    assert build.json_bytes == SNAPSHOT.read_bytes(), "AC1 snapshot is stale"
    assert build.snapshot.cap_release_digest == (
        "sha256:3104ce0ca902bf2aeff7954fc175bd6632adc5b5e56a56011d7a0adf6f89a0ae"
    )
    assert build.snapshot.market_coverage_release_digest == (
        "sha256:ad621c183b893b54f8aec930ac225066aa9f288c161fdf6a0587e115f1b23463"
    )


def test_ac2_corporate_v2_snapshot_keeps_provider_path_identities_separate() -> None:
    rows = build_selection_snapshot(INPUT, ROOT).snapshot.rows

    assert {(str(row.provider_id), str(row.access_path_id)) for row in rows} == {
        ("alpha-vantage", "alpha-vantage-corporate-actions-qveris"),
        ("eodhd", "eodhd-corporate-actions-qveris"),
        ("massive-stocks", "massive-stocks-corporate-actions-qveris"),
        ("twelve-data", "twelve-data-corporate-actions-qveris"),
    }, "AC2 Provider and Access Path identity drifted"
    assert all(row.run_observations.planned_observations == 6 for row in rows)
    assert all(row.run_observations.terminal_observations == 6 for row in rows)


def test_ac3_corporate_v2_snapshot_preserves_nine_market_evidence_states() -> None:
    rows = build_selection_snapshot(INPUT, ROOT).snapshot.rows

    for row in rows:
        results = row.market_coverage.results
        assert {str(result.market) for result in results} == MARKETS
        assert all(result.total_rounds == 2 for result in results)
        for result in results:
            if result.state == "not_applicable":
                assert result.applicability_reason
                assert not result.evidence_refs
            else:
                assert len(result.evidence_refs) == 2
    states = {result.state for row in rows for result in row.market_coverage.results}
    assert "evidence_insufficient" in states
    assert states <= {
        "verified",
        "provider_negative",
        "not_applicable",
        "evidence_insufficient",
    }


def test_ac4_corporate_v2_snapshot_uses_inspect_prices_not_account_costs() -> None:
    rows = build_selection_snapshot(INPUT, ROOT).snapshot.rows
    prices = {
        str(row.provider_id): row.qveris_list_price.amount_credits for row in rows
    }

    assert prices == {
        "alpha-vantage": 2.0,
        "eodhd": 2.81,
        "massive-stocks": 1.0,
        "twelve-data": 2.37,
    }
    for row in rows:
        assert row.qveris_list_price.source == "qveris_inspect"
        assert row.gateway_metrics.cost_sample_size == 0
        assert row.gateway_metrics.median_credits is None
        assert not row.gateway_metrics.cost_evidence_refs

    for relative_root in (
        "evidence/corporate-actions-v2-baseline-2026-q3-v1",
        "evidence/corporate-actions-v2-nine-market-2026-q3-v1",
        "releases/corporate-actions-v2-baseline-2026-q3-v1",
        "releases/corporate-actions-v2-nine-market-2026-q3-v1",
    ):
        for path in (ROOT / relative_root).glob("*.json"):
            assert '"cost_credits"' not in path.read_text(encoding="utf-8")


def test_ac5_corporate_v2_snapshot_builds_through_installed_cli(tmp_path: Path) -> None:
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
    document = json.loads(output.read_text(encoding="utf-8"))
    assert len(document["rows"]) == 4
