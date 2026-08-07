from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from qveris_bench.profiles.builder import build_profile

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
