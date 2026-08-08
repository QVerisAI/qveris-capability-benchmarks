from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from qveris_bench.models.enums import CellState, DimensionState, RunMode
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.profiles.builder import build_profile
from qveris_bench.releases.builder import build_release

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "profiles/company-research-agent.yaml"


def test_ac3_profile_build_is_deterministic_and_evidence_bound() -> None:
    first = build_profile(INPUT, ROOT)
    second = build_profile(INPUT, ROOT)

    assert first.json_bytes == second.json_bytes
    assert first.markdown_bytes == second.markdown_bytes
    profile = first.profile
    assert profile.profile_id == "company-research-agent-profile-v1"
    assert profile.scenario_ref.scenario_id == "company-research-agent"
    assert profile.scenario_ref.version == "1.1.0"
    for dimension in profile.cap_dimensions:
        assert dimension.dimension_state.value in {
            "measured",
            "declared",
            "evidence_insufficient",
        }
        if dimension.dimension_state.value == "measured":
            assert dimension.evidence_refs
    _assert_no_aggregate_keys(json.loads(first.json_bytes))


def test_ac4_profile_keeps_missing_dimensions_insufficient() -> None:
    profile = build_profile(INPUT, ROOT).profile

    dimensions = {(d.cap_id, d.dimension): d for d in profile.cap_dimensions}
    for cap_id in {"stock-quote", "financial-statement-facts", "sec-filing-evidence"}:
        assert (cap_id, "latency") in dimensions
        assert (
            dimensions[(cap_id, "latency")].dimension_state.value
            == "evidence_insufficient"
        )
        assert (cap_id, "cost") in dimensions
        assert (
            dimensions[(cap_id, "cost")].dimension_state.value
            == "evidence_insufficient"
        )


def test_ac7_profile_marks_gateway_latency_and_cost_measured(tmp_path: Path) -> None:
    release_path = _release_with_gateway_metrics(tmp_path)
    profile_input = tmp_path / "profile.yaml"
    profile_input.write_text(
        "\n".join(
            [
                "profile_id: gateway-metrics-profile",
                "version: 1.0.0",
                "scenario_ref:",
                "  scenario_id: company-research-agent",
                "  version: 1.1.0",
                "cap_releases:",
                "  financial-statement-facts:",
                f"    release: {release_path.name}",
                f"    digest: sha256:{_sha256(release_path.read_bytes())}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    profile = build_profile(profile_input, tmp_path).profile

    dimensions = {d.dimension: d for d in profile.cap_dimensions}
    latency = dimensions["latency"]
    cost = dimensions["cost"]
    assert latency.dimension_state is DimensionState.MEASURED
    assert cost.dimension_state is DimensionState.MEASURED
    assert latency.details["measurement_boundary"] == "qveris_gateway"
    assert cost.details["measurement_boundary"] == "qveris_gateway"
    assert latency.details["unit"] == "ms"
    assert cost.details["unit"] == "credits"
    assert latency.evidence_refs and cost.evidence_refs
    assert (latency.details["min_ms"], latency.details["max_ms"]) == (110.0, 310.0)
    assert cost.details["total_credits"] == 3.42
    assert all(
        dimension.dimension_state is DimensionState.EVIDENCE_INSUFFICIENT
        for dimension in (dimensions["reliability"], dimensions["agent-interface"])
    )


def test_ac5_profile_emits_markdown_with_per_cap_tradeoffs() -> None:
    built = build_profile(INPUT, ROOT)

    markdown = built.markdown_bytes.decode()
    assert "# company-research-agent-profile-v1 — Task Fit Profile" in markdown
    assert "stock-quote" in markdown
    assert "financial-statement-facts" in markdown
    assert "sec-filing-evidence" in markdown
    assert "evidence_insufficient" in markdown
    assert "no provider total" in markdown


def test_ac6_profile_build_runs_through_the_installed_cli(tmp_path: Path) -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None
    output = tmp_path / "profile-out"

    result = subprocess.run(
        [
            executable,
            "profile",
            "build",
            "--input",
            str(INPUT),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output / "profile.json").is_file()
    assert (output / "profile.md").is_file()


def _assert_no_aggregate_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            assert not any(
                token in normalized for token in ("score", "rating", "agentfriendly")
            ), key
            _assert_no_aggregate_keys(nested)
    elif isinstance(value, list):
        for item in value:
            _assert_no_aggregate_keys(item)


def _sha256(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _release_with_gateway_metrics(tmp_path: Path) -> Path:
    suite_fingerprint = "9" * 64
    cells: list[RunCell] = []
    evidence: list[EvidenceBundle] = []
    for round_number, (latency_ms, cost_credits) in enumerate(
        ((110.0, 0.32), (310.0, 1.1), (210.0, 2.0)), start=1
    ):
        run_key = (
            f"financial-statements-v1:{suite_fingerprint}:"
            "aapl-revenue-fy2025:financial-modeling-prep:"
            f"fmp-income-statement:direct:{round_number}"
        )
        cells.append(
            RunCell(
                run_key=run_key,
                case_id="aapl-revenue-fy2025",
                provider_id="financial-modeling-prep",
                access_path_id="fmp-income-statement",
                mode=RunMode.DIRECT,
                round=round_number,
                state=CellState.COMPLETED,
            )
        )
        evidence.append(
            EvidenceBundle(
                evidence_id=f"fmp-income-statement-aapl-revenue-{round_number}",
                run_key=run_key,
                raw_digest="sha256:" + hex(round_number)[2:] * 64,
                public_digest="sha256:" + hex(round_number + 10)[2:] * 64,
                redaction_status="sanitized",
                disclosure_level="sanitized_public",
                license_status="cleared",
                extractor_version="1.0.0",
                suite_fingerprint=suite_fingerprint,
                latency_ms=latency_ms,
                cost_credits=cost_credits,
            )
        )
    release = BenchmarkRelease(
        release_id="gateway-metrics-release",
        version="1.0.0",
        suite_fingerprint=suite_fingerprint,
        run_plan_digest="sha256:" + "0" * 64,
        evidence_ids=tuple(bundle.evidence_id for bundle in evidence),
    )
    path = tmp_path / "release.json"
    path.write_bytes(build_release(release, tuple(cells), tuple(evidence)))
    return path
