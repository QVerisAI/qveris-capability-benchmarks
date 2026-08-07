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
PACK = ROOT / "cap_packs/stock_quote_family"
BINDINGS_REGISTRY = ROOT / "cap_packs/qveris-direct-bindings-stock-quote-family.json"

CASE_TO_QUESTION = {
    "aapl-quote": "stock-quote-aapl-current",
    "invalid-stock": "stock-quote-invalid-symbol",
    "aapl-freshness-precision": "stock-quote-aapl-freshness-precision",
    "cn-600519-market-coverage": "stock-quote-600519-market-coverage",
    "cn-600519-agent-contract": "stock-quote-600519-agent-contract",
}

BINDING_CASES: dict[str, tuple[str, str, str, dict[str, object]]] = {
    "finnhub-aapl-quote-family": (
        "finnhub-stock-quote",
        "finnhub",
        "aapl-quote",
        {"symbol": "AAPL"},
    ),
    "finnhub-invalid-stock-family": (
        "finnhub-stock-quote",
        "finnhub",
        "invalid-stock",
        {"symbol": "NOTASTOCK"},
    ),
    "finnhub-aapl-freshness-family": (
        "finnhub-stock-quote",
        "finnhub",
        "aapl-freshness-precision",
        {"symbol": "AAPL"},
    ),
    "finnhub-600519-coverage-family": (
        "finnhub-stock-quote",
        "finnhub",
        "cn-600519-market-coverage",
        {"symbol": "600519.SH"},
    ),
    "finnhub-600519-agent-family": (
        "finnhub-stock-quote",
        "finnhub",
        "cn-600519-agent-contract",
        {"symbol": "600519.SH"},
    ),
    "eodhd-aapl-quote-family": (
        "eodhd-stock-quote",
        "eodhd",
        "aapl-quote",
        {"s": "AAPL.US", "page[limit]": 1},
    ),
    "eodhd-invalid-stock-family": (
        "eodhd-stock-quote",
        "eodhd",
        "invalid-stock",
        {"s": "NOTASTOCK.US", "page[limit]": 1},
    ),
    "eodhd-aapl-freshness-family": (
        "eodhd-stock-quote",
        "eodhd",
        "aapl-freshness-precision",
        {"s": "AAPL.US", "page[limit]": 1},
    ),
    "eodhd-600519-coverage-family": (
        "eodhd-stock-quote",
        "eodhd",
        "cn-600519-market-coverage",
        {"s": "600519.SH", "page[limit]": 1},
    ),
    "eodhd-600519-agent-family": (
        "eodhd-stock-quote",
        "eodhd",
        "cn-600519-agent-contract",
        {"s": "600519.SH", "page[limit]": 1},
    ),
}


def test_ac1_production_suite_expands_to_thirty_direct_cells() -> None:
    first = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers")
    second = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers")

    assert len(first.run_plan.cells) == 30, (
        "AC1 five cases by two included paths by three rounds must expand to 30 cells"
    )
    assert all(cell.applicable for cell in first.run_plan.cells), (
        "AC1 every production Direct cell must be applicable"
    )
    keys = [cell.run_key for cell in first.run_plan.cells]
    assert len(keys) == len(set(keys)), "AC1 run keys must be unique"
    assert keys == [cell.run_key for cell in second.run_plan.cells], (
        "AC1 run keys must be stable across compiles"
    )


def test_ac2_cases_map_one_to_one_to_the_question_family() -> None:
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
    stock_requirement = next(
        requirement
        for requirement in scenario.required_capabilities
        if requirement.cap_id == "stock-quote"
    )
    questions = {
        str(question.question_id): question
        for question in bank.questions
        if question.cap_id == "stock-quote"
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
    assert {str(question.role) for question in questions.values()} == set(
        stock_requirement.minimum_question_roles
    )
    for case in cases:
        question = questions[CASE_TO_QUESTION[str(case.case_id)]]
        assert case.input == question.input, (
            f"AC2 {case.case_id} must share the question input"
        )
        assert set(case.expected_observations).issubset(
            set(question.required_observations)
        ), f"AC2 {case.case_id} must stay within question observations"


def test_ac3_cohort_is_frozen_to_included_quote_paths() -> None:
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )

    assert {path.access_path_id for path in compiled.access_paths} == {
        "finnhub-stock-quote",
        "eodhd-stock-quote",
    }
    assert {cell.access_path_id for cell in compiled.run_plan.cells} == {
        "finnhub-stock-quote",
        "eodhd-stock-quote",
    }
    registry = ProviderRegistryRepository(ROOT / "providers").cohort_check()
    paths = {
        path.access_path_id
        for record in registry
        for path in record.access_paths
        if path.qualification is not None
        and path.qualification.disposition.value == "included"
    }
    assert {"alpha-vantage-stock-quote", "fmp-stock-quote"}.isdisjoint(paths)


def test_ac4_outcome_rules_match_all_case_completion_conditions() -> None:
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )

    for case in compiled.cases:
        expected = (
            ["validation_error"]
            if case.negative_control
            else ["symbol", "price", "timestamp"]
        )
        assert list(case.completion_conditions) == expected, (
            f"AC4 {case.case_id} must match the frozen outcome rules"
        )


def test_ac6_every_case_has_a_frozen_live_binding() -> None:
    registry = BINDINGS_REGISTRY
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )
    suite_path = PACK / "suite.yaml"

    for binding_id, expected in BINDING_CASES.items():
        binding = load_registered_qveris_direct_binding(registry, binding_id)
        validate_qveris_direct_binding(binding, suite_path, ROOT / "providers")
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
    assert "Planned 30 cells, 30 applicable calls" in result.stdout
    assert output.is_file()
