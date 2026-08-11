from pathlib import Path

import yaml

from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.question_bank.repository import load_question_bank
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"

EXPECTED_PATHS = {
    "ifind-native-mcp": "ifind",
    "hangseng-dividends-qveris": "hangseng",
    "twelve-data-dividends-qveris": "twelve-data",
    "alpha-vantage-dividends-qveris": "alpha-vantage",
    "eodhd-dividends-qveris": "eodhd",
    "massive-stocks-dividends-qveris": "massive-stocks",
}

CASE_TO_QUESTION = {
    "aapl-dividends-fixed-window": "dividend-events-aapl-window",
    "cn-600519-dividends-fixed-window": "dividend-events-600519-window",
    "invalid-dividend-symbol": "dividend-events-invalid-symbol",
}


def _compiled():
    return compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers")


def test_ac1_suite_freezes_six_providers_and_six_access_paths() -> None:
    compiled = _compiled()

    paths = {
        str(path.access_path_id): str(path.provider_id)
        for path in compiled.access_paths
    }
    assert paths == EXPECTED_PATHS
    assert "ifind-dividends-qveris" not in paths
    assert [path for path in paths if path.startswith("ifind-")] == ["ifind-native-mcp"]


def test_ac2_market_applicability_produces_three_rounds_of_direct_calls() -> None:
    first = _compiled()
    second = _compiled()

    assert first.suite.rounds >= 3
    assert len(first.run_plan.cells) == 54
    assert sum(cell.applicable for cell in first.run_plan.cells) == 36
    assert all(cell.mode.value == "direct" for cell in first.run_plan.cells)
    assert [cell.run_key for cell in first.run_plan.cells] == [
        cell.run_key for cell in second.run_plan.cells
    ]
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/live-dividend-events-e2e.yml").read_text()
    )
    assert workflow["jobs"]["direct"]["strategy"]["matrix"]["round"] == [1, 2, 3]

    applicable = {
        (cell.case_id, cell.provider_id)
        for cell in first.run_plan.cells
        if cell.applicable
    }
    assert applicable == {
        ("aapl-dividends-fixed-window", provider_id)
        for provider_id in (
            "twelve-data",
            "alpha-vantage",
            "eodhd",
            "massive-stocks",
        )
    } | {
        ("cn-600519-dividends-fixed-window", provider_id)
        for provider_id in ("ifind", "hangseng")
    } | {
        ("invalid-dividend-symbol", provider_id)
        for provider_id in EXPECTED_PATHS.values()
    }


def test_ac3_cases_preserve_question_bank_provenance() -> None:
    bank = load_question_bank(ROOT / "question_bank")
    questions = {
        str(question.question_id): question
        for question in bank.questions
        if question.cap_id == "dividend-events"
    }
    cases = {str(case.case_id): case for case in _compiled().cases}

    assert set(cases) == set(CASE_TO_QUESTION)
    for case_id, question_id in CASE_TO_QUESTION.items():
        question = questions[question_id]
        case = cases[case_id]
        assert case.input == question.input
        assert set(case.expected_observations).issubset(
            set(question.required_observations)
        )


def test_ac4_every_scoped_path_has_execution_qualification() -> None:
    records = ProviderRegistryRepository(ROOT / "providers").cohort_check()
    paths = {
        str(path.access_path_id): path
        for record in records
        for path in record.access_paths
    }

    for path_id, provider_id in EXPECTED_PATHS.items():
        path = paths[path_id]
        assert str(path.provider_id) == provider_id
        assert path.qualification is not None
        assert path.qualification.disposition.value == "included"
        assert str(path.qualification.evidence_digest).startswith("sha256:")
