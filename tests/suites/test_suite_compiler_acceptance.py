from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from qveris_bench.models.enums import CellState, RunMode
from qveris_bench.suites.compiler import (
    SuiteCompilationError,
    compile_suite,
    write_frozen_suite,
    write_run_plan,
)
from qveris_bench.suites.fingerprint import ResumeFingerprintError


def _provider_data(
    provider_id: str,
    access_path_id: str,
    path_type: str,
    agent_eligible: bool,
    digest_char: str,
) -> dict:
    return {
        "provider": {
            "provider_id": provider_id,
            "official_name": provider_id.replace("-", " ").title(),
            "website": f"https://{provider_id}.example.com/",
            "market_coverage": ["US"],
            "testing_authorization": "Approved internal benchmark plan",
            "qveris_integration": False,
        },
        "access_paths": [
            {
                "access_path_id": access_path_id,
                "provider_id": provider_id,
                "path_type": path_type,
                "credential_env": [],
                "official_source": f"https://{provider_id}.example.com/docs",
                "canonical_interface": "get-holdings",
                "agent_trial_eligible": agent_eligible,
                "qualification": {
                    "disposition": "included",
                    "reason": "Official machine interface is available for testing.",
                    "evidence_digest": "sha256:" + digest_char * 64,
                },
            }
        ],
    }


def _write_inputs(
    root: Path, explicit_not_applicable: bool = False
) -> tuple[Path, Path, Path]:
    providers_root = root / "providers"
    for directory, data in (
        (
            "fmp",
            _provider_data(
                "financial-modeling-prep",
                "fmp-official-api",
                "official_api",
                False,
                "a",
            ),
        ),
        (
            "demo",
            _provider_data(
                "demo-market-data",
                "demo-native-mcp",
                "native_mcp",
                True,
                "b",
            ),
        ),
    ):
        path = providers_root / directory / "provider.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False))

    cases_path = root / "cap_pack" / "cases.yaml"
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(
        yaml.safe_dump(
            {
                "cases": [
                    {
                        "case_id": "spy-holdings",
                        "cap_id": "etf-holdings",
                        "question": "Return current SPY holdings.",
                        "input": {"symbol": "SPY"},
                        "expected_observations": ["holding identifiers"],
                        "completion_conditions": ["non-empty holdings"],
                    },
                    {
                        "case_id": "invalid-symbol",
                        "cap_id": "etf-holdings",
                        "question": "Handle an invalid ETF symbol.",
                        "input": {"symbol": "INVALID_ETF_123"},
                        "negative_control": True,
                        "expected_observations": ["error semantics"],
                        "completion_conditions": ["evidenced negative response"],
                    },
                ]
            },
            sort_keys=False,
        )
    )

    cap_path = root / "cap_pack" / "cap.yaml"
    cap_path.write_text(
        yaml.safe_dump(
            {
                "cap_id": "etf-holdings",
                "version": "1.0.0",
                "name": "ETF Holdings",
                "business_use": "Compare constituent-level ETF data providers.",
                "scope": ["US-listed ETFs"],
                "sources": [{"source_type": "qveris_original"}],
            },
            sort_keys=False,
        )
    )

    suite = {
        "suite_id": "etf-holdings-v1",
        "version": "1.0.0",
        "cap_id": "etf-holdings",
        "cap_version": "1.0.0",
        "case_ids": ["spy-holdings", "invalid-symbol"],
        "access_path_ids": ["fmp-official-api", "demo-native-mcp"],
        "modes": ["direct", "agent_trial"],
        "rounds": 2,
        "environment": {"region": "us-east"},
        "agent_protocol": {
            "model": "gpt-test",
            "prompt_version": "1.0.0",
            "canonical_tool": "get-holdings",
            "maximum_calls": 3,
            "token_budget": 2000,
            "timeout_seconds": 60,
        },
        "not_applicable": [],
    }
    if explicit_not_applicable:
        suite["not_applicable"] = [
            {
                "case_id": "invalid-symbol",
                "access_path_id": "demo-native-mcp",
                "mode": "direct",
                "reason": "Demo sandbox does not expose negative controls.",
            }
        ]
    suite_path = root / "cap_pack" / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False))
    return suite_path, cases_path, providers_root


def test_ac1_matrix_expands_every_case_path_mode_and_round(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)

    compiled = compile_suite(suite_path, cases_path, providers_root)

    assert len(compiled.run_plan.cells) == 16, "AC1 full matrix must retain every cell"
    assert sum(cell.applicable for cell in compiled.run_plan.cells) == 12, (
        "AC1 ineligible Agent cells must remain explicit not_applicable cells"
    )
    assert all(
        cell.state is CellState.PLANNED
        for cell in compiled.run_plan.cells
        if cell.mode is RunMode.DIRECT and cell.applicable
    ), "AC1 every applicable Direct cell must be planned"


def test_ac2_explicit_not_applicable_cells_remain_in_matrix(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(
        tmp_path, explicit_not_applicable=True
    )

    compiled = compile_suite(suite_path, cases_path, providers_root)
    cells = [
        cell
        for cell in compiled.run_plan.cells
        if cell.case_id == "invalid-symbol"
        and cell.access_path_id == "demo-native-mcp"
        and cell.mode is RunMode.DIRECT
    ]

    assert len(cells) == 2, "AC2 explicit N/A must preserve every round"
    assert all(
        not cell.applicable and cell.state is CellState.NOT_APPLICABLE for cell in cells
    ), "AC2 explicit N/A cells must be terminal and non-applicable"


def test_ac3_run_keys_are_unique_and_stable(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)

    first = compile_suite(suite_path, cases_path, providers_root)
    second = compile_suite(suite_path, cases_path, providers_root)
    first_keys = [cell.run_key for cell in first.run_plan.cells]
    second_keys = [cell.run_key for cell in second.run_plan.cells]

    assert len(first_keys) == len(set(first_keys)), "AC3 run keys must be unique"
    assert first_keys == second_keys, "AC3 run keys must be stable"


def test_ac4_missing_case_or_access_path_reference_fails_closed(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    suite = yaml.safe_load(suite_path.read_text())
    suite["case_ids"].append("missing-case")
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False))

    with pytest.raises(SuiteCompilationError, match="missing-case"):
        compile_suite(suite_path, cases_path, providers_root)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("modes", ["agent_trial"]),
        ("case_ids", ["spy-holdings", "spy-holdings"]),
        ("access_path_ids", ["fmp-official-api", "fmp-official-api"]),
        ("modes", ["direct", "direct"]),
    ],
)
def test_ac4_direct_mode_and_unique_selectors_are_required(
    tmp_path: Path, field: str, value: list[str]
) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    suite = yaml.safe_load(suite_path.read_text())
    suite[field] = value
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False))

    with pytest.raises(ValueError, match=field):
        compile_suite(suite_path, cases_path, providers_root)


def test_ac4_not_applicable_rule_must_reference_frozen_matrix(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    suite = yaml.safe_load(suite_path.read_text())
    suite["not_applicable"] = [
        {
            "case_id": "unknown-case",
            "access_path_id": "demo-native-mcp",
            "reason": "This invalid rule must not be ignored.",
        }
    ]
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False))

    with pytest.raises(ValueError, match="unknown-case"):
        compile_suite(suite_path, cases_path, providers_root)


def test_ac4_agent_tool_must_match_eligible_canonical_interface(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    suite = yaml.safe_load(suite_path.read_text())
    suite["agent_protocol"]["canonical_tool"] = "different-tool"
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False))

    with pytest.raises(SuiteCompilationError, match="different-tool"):
        compile_suite(suite_path, cases_path, providers_root)


def test_ac4_cap_version_must_match_cap_definition(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    suite = yaml.safe_load(suite_path.read_text())
    suite["cap_version"] = "9.9.9"
    suite_path.write_text(yaml.safe_dump(suite, sort_keys=False))

    with pytest.raises(SuiteCompilationError, match="9.9.9"):
        compile_suite(suite_path, cases_path, providers_root)


def test_ac4_duplicate_yaml_keys_fail_closed(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    suite_path.write_text("suite_id: duplicate\n" + suite_path.read_text())

    with pytest.raises(ValueError, match="duplicate key"):
        compile_suite(suite_path, cases_path, providers_root)


def test_ac5_frozen_and_run_plan_outputs_are_canonical(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    compiled = compile_suite(suite_path, cases_path, providers_root)
    frozen_path = tmp_path / "suite.frozen.json"
    run_plan_path = tmp_path / "run-plan.json"

    write_frozen_suite(compiled, frozen_path)
    write_run_plan(compiled, run_plan_path)
    first_frozen = frozen_path.read_bytes()
    first_plan = run_plan_path.read_bytes()
    write_frozen_suite(compiled, frozen_path)
    write_run_plan(compiled, run_plan_path)

    assert frozen_path.read_bytes() == first_frozen, (
        "AC5 frozen suite JSON must be byte-identical"
    )
    assert run_plan_path.read_bytes() == first_plan, (
        "AC5 Run Plan JSON must be byte-identical"
    )
    assert json.loads(first_plan)["suite_fingerprint"] == compiled.fingerprint, (
        "AC5 Run Plan must bind the frozen fingerprint"
    )


def test_ac7_resume_rejects_different_suite_fingerprint(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    compiled = compile_suite(suite_path, cases_path, providers_root)

    with pytest.raises(ResumeFingerprintError):
        compiled.assert_resume_fingerprint("f" * 64)


def test_ac8_installed_cli_freezes_and_plans_suite(tmp_path: Path) -> None:
    suite_path, cases_path, providers_root = _write_inputs(tmp_path)
    frozen_path = tmp_path / "suite.frozen.json"
    run_plan_path = tmp_path / "run-plan.json"
    executable = shutil.which("qveris-bench")
    assert executable is not None, "AC8 installed CLI is required"
    shared = [
        str(suite_path),
        "--cases",
        str(cases_path),
        "--providers-root",
        str(providers_root),
    ]

    freeze_result = subprocess.run(
        [executable, "suite", "freeze", *shared, "--output", str(frozen_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    plan_result = subprocess.run(
        [executable, "suite", "plan", *shared, "--output", str(run_plan_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert freeze_result.returncode == 0, (
        f"AC8 suite freeze failed: {freeze_result.stderr}"
    )
    assert plan_result.returncode == 0, f"AC8 suite plan failed: {plan_result.stderr}"
    assert frozen_path.stat().st_size > 0, "AC8 frozen suite must be non-empty"
    assert run_plan_path.stat().st_size > 0, "AC8 Run Plan must be non-empty"
    assert "12 applicable calls" in plan_result.stdout, (
        "AC8 plan output must report the call count"
    )
