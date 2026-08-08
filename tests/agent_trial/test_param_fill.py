"""Acceptance tests for the agent parameter-fill operator."""

from __future__ import annotations

from qveris_bench.agent_trial.param_fill import (
    AgentQuestion,
    ParamSpec,
    ToolContract,
    evaluate_tool_call,
    run_probe,
)


def _contract() -> ToolContract:
    return ToolContract(
        tool_id="finnhub.quote.retrieve.v1.f72cf5ef",
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
