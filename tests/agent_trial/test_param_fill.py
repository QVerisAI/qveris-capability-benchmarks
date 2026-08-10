"""Acceptance tests for the agent parameter-fill operator."""

from __future__ import annotations

from qveris_bench.agent_trial.param_fill import (
    AgentQuestion,
    FailureMode,
    ParamSpec,
    ToolContract,
    classify_failure,
    evaluate_tool_call,
    run_probe,
)


def _contract() -> ToolContract:
    return ToolContract(
        tool_id="finnhub.quote.retrieve.v1.f72cf5ef",
        provider_id="finnhub",
        access_path_id="finnhub-stock-quote",
        name="Quote",
        description="Get real-time quote data for US stocks.",
        params=(ParamSpec(name="symbol", type="string", required=True),),
    )


def _question() -> AgentQuestion:
    return AgentQuestion(
        question_id="stock-quote-aapl-current",
        task="Return the current quote for AAPL.",
        expected_params={"symbol": "AAPL"},
    )


def _tool_call(
    arguments: str, tool_id: str = "finnhub.quote.retrieve.v1.f72cf5ef"
) -> dict:
    return {
        "tool_calls": [
            {"function": {"name": tool_id, "arguments": arguments}},
        ]
    }


def test_ac1_valid_tool_call_passes_all_checks() -> None:
    result = evaluate_tool_call(
        _contract(), _question(), _tool_call('{"symbol": "AAPL"}')
    )
    assert result.passed, result.checks
    assert result.checks.single_tool and result.checks.required_present
    assert result.checks.value_valid and result.checks.no_forbidden
    assert result.checks.semantics_match
    assert result.failure_mode == FailureMode.PASS.value


def test_ac2_missing_required_param_fails_required_present() -> None:
    result = evaluate_tool_call(_contract(), _question(), _tool_call("{}"))
    assert not result.checks.required_present
    assert not result.passed


def test_ac3_hallucinated_extra_param_fails_no_forbidden() -> None:
    result = evaluate_tool_call(
        _contract(), _question(), _tool_call('{"symbol": "AAPL", "market": "HK"}')
    )
    assert not result.checks.no_forbidden
    assert not result.passed
    assert result.failure_mode == FailureMode.FORBIDDEN_PARAM.value


def test_ac9_failure_modes_are_classified() -> None:
    cases = [
        (
            _tool_call("{}"),
            FailureMode.MISSING_REQUIRED.value,
        ),
        (
            {"tool_calls": []},
            FailureMode.NO_TOOL_CALL.value,
        ),
        (
            {
                "tool_calls": [
                    {"function": {"name": "a.tool.v1", "arguments": "{}"}},
                    {"function": {"name": "b.tool.v1", "arguments": "{}"}},
                ]
            },
            FailureMode.MULTIPLE_TOOLS.value,
        ),
        (
            {
                "tool_calls": [
                    {"function": {"name": "other.tool.v1", "arguments": "{}"}}
                ]
            },
            FailureMode.WRONG_TOOL.value,
        ),
        (
            _tool_call("{not json"),
            FailureMode.MALFORMED_ARGUMENTS.value,
        ),
        (
            _tool_call('{"symbol": 123}'),
            FailureMode.TYPE_INVALID.value,
        ),
        (
            _tool_call('{"symbol": "MSFT"}'),
            FailureMode.SEMANTICS_MISMATCH.value,
        ),
    ]
    for message, expected in cases:
        result = evaluate_tool_call(_contract(), _question(), message)
        assert classify_failure(result) == expected, message


def test_ac10_difficulty_defaults_and_run_probe_records_it() -> None:
    def llm_fn(question, contract):
        return _tool_call('{"symbol": "AAPL"}')

    results = run_probe(_contract(), (_question(),), llm_fn, rounds=1)
    assert results[0].difficulty == "L1"


def test_ac4_no_tool_call_or_wrong_tool_fails_single_tool() -> None:
    no_call = evaluate_tool_call(_contract(), _question(), {})
    assert not no_call.checks.single_tool and not no_call.passed
    wrong = evaluate_tool_call(
        _contract(), _question(), _tool_call("{}", tool_id="other.tool")
    )
    assert not wrong.checks.single_tool and not wrong.passed


def test_ac5_invalid_value_type_fails_value_valid() -> None:
    result = evaluate_tool_call(_contract(), _question(), _tool_call('{"symbol": 42}'))
    assert not result.checks.value_valid
    assert not result.passed


def test_ac6_symbol_case_normalized() -> None:
    result = evaluate_tool_call(
        _contract(), _question(), _tool_call('{"symbol": "aapl"}')
    )
    assert result.checks.semantics_match and result.passed


def test_ac7_run_probe_records_rounds_and_model() -> None:
    def llm_fn(question, contract):
        return _tool_call('{"symbol": "AAPL"}')

    results = run_probe(
        _contract(),
        (_question(),),
        llm_fn,
        rounds=2,
        model="test-model",
    )
    assert len(results) == 2
    assert all(result.model == "test-model" for result in results)
    assert {result.round for result in results} == {1, 2}
    assert all(result.passed for result in results)


def test_ac8_array_param_semantics_normalized() -> None:
    contract = ToolContract(
        tool_id="hangseng.stock.dividend.query.v1",
        provider_id="example-provider",
        access_path_id="example-dividends",
        name="Stock Dividend Query",
        description="Query dividend records.",
        params=(ParamSpec(name="stockObject", type="array", required=True),),
    )
    question = AgentQuestion(
        question_id="corp-actions-600519-dividends",
        task="获取贵州茅台过去一年的分红记录。",
        expected_params={"stockObject": "600519.SH"},
    )
    result = evaluate_tool_call(
        contract,
        question,
        _tool_call(
            '{"stockObject": ["600519.SH"]}',
            tool_id="hangseng.stock.dividend.query.v1",
        ),
    )
    assert result.checks.value_valid and result.checks.semantics_match
    assert result.passed
