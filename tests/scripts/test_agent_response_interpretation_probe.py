"""Acceptance tests for the response-interpretation probe."""

from __future__ import annotations

from qveris_bench.agent_trial.response_interpretation import (
    InterpretationQuestion,
    evaluate_interpretation,
    run_interpretation_probe,
)
from scripts.agent_response_interpretation_probe import load_fixture


def _question(**kwargs) -> InterpretationQuestion:
    defaults = {
        "question_id": "dividend-aapl-latest",
        "task": "AAPL 最近一次每股分红金额和除息日是什么？",
        "expected_values": {"amount": 0.27, "ex_date": "2026-05-11"},
        "unit_fields": (("amount", "USD"),),
        "negative_control": False,
        "require_timestamp": False,
    }
    defaults.update(kwargs)
    return InterpretationQuestion(**defaults)


_RESPONSE = (
    '{"meta": {"symbol": "AAPL", "currency": "USD"}, '
    '"dividends": [{"ex_date": "2026-05-11", "amount": 0.27}]}'
)


def test_ac1_correct_extraction_passes() -> None:
    answer = "AAPL 最近一次分红每股 0.27 美元，除息日 2026-05-11。"
    checks = evaluate_interpretation(_question(), _RESPONSE, answer)
    assert checks.passed(), checks


def test_ac2_wrong_value_fails_extraction() -> None:
    answer = "AAPL 最近一次分红每股 0.50 美元，除息日 2026-05-11。"
    checks = evaluate_interpretation(_question(), _RESPONSE, answer)
    assert not checks.extraction_correct
    assert not checks.passed()


def test_ac3_extra_ticker_fails_no_hallucination() -> None:
    answer = "AAPL 分红 0.27 美元，除息日 2026-05-11；另外 MSFT 也有分红。"
    checks = evaluate_interpretation(_question(), _RESPONSE, answer)
    assert not checks.no_hallucination


def test_ac4_missing_currency_unit_fails_unit_semantics() -> None:
    answer = "AAPL 最近一次分红每股 0.27，除息日 2026-05-11。"
    checks = evaluate_interpretation(_question(), _RESPONSE, answer)
    assert not checks.unit_semantics


def test_ac9_chinese_date_format_counts_as_correct_extraction() -> None:
    answer = "AAPL 最近一次分红每股 0.27 美元，除息日为 2026年5月11日。"
    checks = evaluate_interpretation(_question(), _RESPONSE, answer)
    assert checks.extraction_correct and checks.passed(), checks


def test_ac5_negative_control_invents_price_fails() -> None:
    response = '{"meta": {"symbol": "NOTASTOCK"}, "dividends": []}'
    answer = "NOTASTOCK 最近分红每股 0.50 美元。"
    checks = evaluate_interpretation(
        _question(
            question_id="dividend-invalid-symbol",
            expected_values={},
            negative_control=True,
        ),
        response,
        answer,
    )
    assert not checks.negative_state


def test_ac6_negative_control_reports_no_data_passes() -> None:
    response = '{"meta": {"symbol": "NOTASTOCK"}, "dividends": []}'
    answer = "该代码没有分红记录。"
    checks = evaluate_interpretation(
        _question(
            question_id="dividend-invalid-symbol",
            expected_values={},
            negative_control=True,
        ),
        response,
        answer,
    )
    assert checks.negative_state and checks.passed(), checks


def test_ac10_negative_control_na_reported_as_zero_fails() -> None:
    response = '{"code": "ZZZUSD.FOREX", "close": "NA", "timestamp": "NA"}'
    answer = "ZZZUSD 的收盘汇率为 0。"
    checks = evaluate_interpretation(
        _question(
            question_id="fx-na-placeholder",
            expected_values={},
            negative_control=True,
        ),
        response,
        answer,
    )
    assert not checks.negative_state


def test_ac7_run_probe_records_rounds() -> None:
    def llm_fn(question, response_text):
        return "AAPL 每股 0.27 美元，除息日 2026-05-11。"

    results = run_interpretation_probe(
        (_question(),),
        {"dividend-aapl-latest": _RESPONSE},
        llm_fn,
        rounds=2,
        model="test-model",
    )
    assert len(results) == 2
    assert all(result.passed for result in results)
    assert {result.round for result in results} == {1, 2}


def test_fixture_loads() -> None:
    from pathlib import Path

    cases = load_fixture(
        Path("scripts/fixtures/agent-response-interpretation-dividends.yaml")
    )
    assert {question.question_id for question, _ in cases} == {
        "dividend-aapl-latest",
        "dividend-invalid-symbol",
    }
