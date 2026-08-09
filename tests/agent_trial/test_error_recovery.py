"""Acceptance tests for the agent error-recovery operator."""

from __future__ import annotations

from qveris_bench.agent_trial.error_recovery import (
    RecoveryQuestion,
    ToolContract,
    evaluate_recovery,
    run_recovery_probe,
)
from qveris_bench.agent_trial.param_fill import ParamSpec


def _contract() -> ToolContract:
    return ToolContract(
        tool_id="twelvedata.exchangerate.retrieve.v1.9eeb3b0d",
        name="Exchange rate",
        description="Real-time exchange rates for currency pairs.",
        params=(ParamSpec(name="symbol", type="string", required=True),),
    )


def _question() -> RecoveryQuestion:
    return RecoveryQuestion(
        question_id="fx-eur-usd-invalid-pair-recovery",
        task="EUR/USD 当前汇率是多少？",
        failure_response='{"status": "error", "message": "not found: EUR/ZZZ"}',
        expected_retry_params={"symbol": "EUR/USD"},
    )


def _message(content: str, arguments: str = '{"symbol": "EUR/USD"}') -> dict:
    return {
        "content": content,
        "tool_calls": [
            {
                "function": {
                    "name": "twelvedata.exchangerate.retrieve.v1.9eeb3b0d",
                    "arguments": arguments,
                }
            }
        ],
    }


def test_ac1_correct_retry_passes() -> None:
    result = evaluate_recovery(
        _contract(), _question(), _message("币对无效，重试正确的 EUR/USD")
    )
    assert result.passed, result.checks
    assert result.checks.single_tool and result.checks.error_identified
    assert result.checks.retry_params_correct and result.checks.no_forbidden


def test_ac2_retry_with_wrong_symbol_fails() -> None:
    result = evaluate_recovery(
        _contract(), _question(), _message("已修正", '{"symbol": "GBP/USD"}')
    )
    assert not result.checks.retry_params_correct
    assert not result.passed


def test_ac3_multiple_tool_calls_fail_single_tool() -> None:
    message = {
        "content": "先重试",
        "tool_calls": [
            {"function": {"name": "a.tool.v1", "arguments": "{}"}},
            {"function": {"name": "b.tool.v1", "arguments": "{}"}},
        ],
    }
    result = evaluate_recovery(_contract(), _question(), message)
    assert not result.checks.single_tool
    assert not result.passed
    assert result.notes.startswith("multiple tool calls")


def test_ac4_no_tool_call_fails() -> None:
    result = evaluate_recovery(_contract(), _question(), {"content": "报错了"})
    assert not result.passed
    assert result.notes == "no tool call"


def test_ac5_wrong_tool_fails() -> None:
    message = {
        "content": "换一个工具",
        "tool_calls": [
            {"function": {"name": "other.tool.v1", "arguments": "{}"}},
        ],
    }
    result = evaluate_recovery(_contract(), _question(), message)
    assert not result.checks.single_tool
    assert result.notes == "wrong tool: other.tool.v1"


def test_ac6_hallucinated_param_fails_no_forbidden() -> None:
    message = _message("已修正", '{"symbol": "EUR/USD", "market": "HK"}')
    result = evaluate_recovery(_contract(), _question(), message)
    assert not result.checks.no_forbidden
    assert not result.passed


def test_ac7_error_explanation_optional_for_pass() -> None:
    result = evaluate_recovery(_contract(), _question(), _message(""))
    assert result.passed, result.checks
    assert not result.checks.error_identified


def test_ac8_run_probe_records_rounds_and_difficulty() -> None:
    def llm_fn(question, contract):
        return _message("币对无效，改用 EUR/USD")

    results = run_recovery_probe(
        _contract(),
        (_question(),),
        llm_fn,
        rounds=2,
        model="test-model",
    )
    assert len(results) == 2
    assert all(result.passed for result in results)
    assert {result.round for result in results} == {1, 2}
    assert all(result.difficulty == "L2" for result in results)
