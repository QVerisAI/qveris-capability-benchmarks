from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from qveris_bench.execution.qveris_binding import (
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.question_bank.repository import load_question_bank
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/financial_statement_facts"
BINDINGS_REGISTRY = ROOT / "cap_packs/qveris-direct-bindings-financial-statements.json"

CASE_TO_QUESTION = {
    "aapl-revenue-fy2025": "financial-statement-facts-aapl-revenue",
    "invalid-period": "financial-statement-facts-invalid-period",
    "cn-600519-market-coverage": "financial-statement-facts-600519-cn-market-coverage",
    "aapl-canonical-identifier": "financial-statement-facts-aapl-canonical-identifier",
    "aapl-fiscal-period-shape": "financial-statement-facts-aapl-fiscal-period-shape",
    "aapl-agent-contract": "financial-statement-facts-aapl-agent-contract",
}

BINDING_CASES: dict[str, tuple[str, str, str, dict[str, object]]] = {
    "fmp-income-statement-aapl-revenue": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "aapl-revenue-fy2025",
        {"symbol": "AAPL", "limit": 5},
    ),
    "fmp-income-statement-invalid-period": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "invalid-period",
        {"symbol": "AAPL", "limit": 5},
    ),
    "fmp-income-statement-cn-600519-market-coverage": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "cn-600519-market-coverage",
        {"symbol": "600519.SS", "limit": 5},
    ),
    "fmp-income-statement-aapl-canonical-identifier": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "aapl-canonical-identifier",
        {"symbol": "AAPL", "limit": 5},
    ),
    "fmp-income-statement-aapl-fiscal-period-shape": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "aapl-fiscal-period-shape",
        {"symbol": "AAPL", "limit": 5},
    ),
    "fmp-income-statement-aapl-agent-contract": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "aapl-agent-contract",
        {"symbol": "AAPL", "limit": 5},
    ),
}


def test_ac1_fsf_suite_expands_to_eighteen_direct_cells() -> None:
    first = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers")
    second = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers")

    assert len(first.run_plan.cells) == 18, (
        "AC1 six cases by one included path by three rounds must expand to 18 cells"
    )
    assert all(cell.applicable for cell in first.run_plan.cells)
    keys = [cell.run_key for cell in first.run_plan.cells]
    assert len(keys) == len(set(keys))
    assert keys == [cell.run_key for cell in second.run_plan.cells]


def test_ac2_cases_map_one_to_one_to_fsf_questions() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    scenario = next(
        scenario
        for scenario in bank.scenarios
        if (scenario.scenario_id, scenario.version)
        == (
            "company-research-agent",
            "1.1.0",
        )
    )
    questions = {
        str(question.question_id): question
        for question in bank.questions
        if question.cap_id == "financial-statement-facts"
        and any(
            reference.scenario_id == scenario.scenario_id
            and reference.version == scenario.version
            for reference in question.scenario_refs
        )
    }
    cases = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    ).cases

    assert set(CASE_TO_QUESTION) == {str(case.case_id) for case in cases}
    assert set(CASE_TO_QUESTION.values()) == set(questions)
    for case in cases:
        question = questions[CASE_TO_QUESTION[str(case.case_id)]]
        assert case.input == question.input
        assert set(case.expected_observations).issubset(
            set(question.required_observations)
        )


def test_ac3_cohort_is_frozen_to_included_fsf_paths() -> None:
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )

    assert {path.access_path_id for path in compiled.access_paths} == {
        "fmp-income-statement",
    }
    ProviderRegistryRepository(ROOT / "providers").cohort_check()
    for path in compiled.access_paths:
        assert path.qualification is not None
        assert path.qualification.disposition.value == "included"
        assert path.qualification.evidence_digest.startswith("sha256:")


def test_ac4_outcome_rules_match_case_completion_conditions() -> None:
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )

    for case in compiled.cases:
        expected = (
            ["validation_error"]
            if case.negative_control
            else ["symbol", "fiscal_year", "revenue"]
        )
        assert list(case.completion_conditions) == expected


def test_ac6_every_case_has_a_frozen_live_binding() -> None:
    registry = BINDINGS_REGISTRY
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )

    for binding_id, expected in BINDING_CASES.items():
        binding = load_registered_qveris_direct_binding(registry, binding_id)
        validate_qveris_direct_binding(binding, PACK / "suite.yaml", ROOT / "providers")
        assert binding.access_path_id == expected[0]
        assert binding.provider_id == expected[1]
        assert binding.parameters == expected[3]
        assert any(
            cell.case_id == expected[2]
            and cell.access_path_id == binding.access_path_id
            for cell in compiled.run_plan.cells
        ), f"AC6 {binding_id} must resolve to a frozen RunCell"


def test_ac6_suite_plan_runs_through_the_installed_cli(tmp_path: Path) -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None
    output = tmp_path / "run-plan.json"

    result = subprocess.run(
        [
            executable,
            "suite",
            "plan",
            str(PACK / "suite.yaml"),
            "--cases",
            str(PACK / "cases.yaml"),
            "--providers-root",
            str(ROOT / "providers"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Planned 18 cells, 18 applicable calls" in result.stdout
    assert output.is_file()
