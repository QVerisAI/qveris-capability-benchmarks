"""Agent error-recovery evaluation: read a failed response, fix params, retry."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from qveris_bench.agent_trial.param_fill import (
    ToolContract,
    extract_tool_call,
    normalize_value,
    sanitize_tool_name,
)


@dataclass(frozen=True)
class RecoveryQuestion:
    question_id: str
    task: str
    failure_response: str
    expected_retry_params: dict[str, str] = field(default_factory=dict)
    forbidden_params: tuple[str, ...] = ()
    difficulty: str = "L2"


@dataclass(frozen=True)
class RecoveryChecks:
    single_tool: bool
    error_identified: bool
    retry_params_correct: bool
    no_forbidden: bool

    def passed(self) -> bool:
        return all(
            (
                self.single_tool,
                self.retry_params_correct,
                self.no_forbidden,
            )
        )


@dataclass(frozen=True)
class RecoveryResult:
    question_id: str
    round: int
    model: str
    content: str
    tool_call: dict[str, Any] | None
    checks: RecoveryChecks
    passed: bool
    notes: str = ""
    difficulty: str = "L2"
    provider_id: str = ""
    access_path_id: str = ""


_ERROR_SIGNALS = (
    "not found",
    "invalid",
    "error",
    "fail",
    "wrong",
    "retry",
    "correct",
    "无数据",
    "无效",
    "未找到",
    "失败",
    "错误",
    "修正",
    "重试",
    "改为",
    "换成",
    "不存在",
)


def _error_identified(content: str) -> bool:
    lowered = content.lower()
    return any(signal in lowered for signal in _ERROR_SIGNALS)


def evaluate_recovery(
    contract: ToolContract,
    question: RecoveryQuestion,
    message: dict[str, Any],
) -> RecoveryResult:
    """Score one model message that explains the failure and retries the tool."""
    content = str(message.get("content") or "")
    tool_call, note = extract_tool_call(message)
    checks = RecoveryChecks(
        single_tool=False,
        error_identified=_error_identified(content),
        retry_params_correct=False,
        no_forbidden=False,
    )
    if tool_call is None:
        return RecoveryResult(
            question_id=question.question_id,
            round=0,
            model="",
            content=content,
            tool_call=None,
            checks=checks,
            passed=False,
            notes=note,
        )

    function = tool_call.get("function") or {}
    if function.get("name") not in {
        contract.tool_id,
        sanitize_tool_name(contract.tool_id),
    }:
        return RecoveryResult(
            question_id=question.question_id,
            round=0,
            model="",
            content=content,
            tool_call=tool_call,
            checks=checks,
            passed=False,
            notes=f"wrong tool: {function.get('name')}",
        )
    try:
        arguments = json.loads(function.get("arguments") or "{}")
    except json.JSONDecodeError:
        return RecoveryResult(
            question_id=question.question_id,
            round=0,
            model="",
            content=content,
            tool_call=tool_call,
            checks=checks,
            passed=False,
            notes="malformed arguments",
        )
    if not isinstance(arguments, dict):
        return RecoveryResult(
            question_id=question.question_id,
            round=0,
            model="",
            content=content,
            tool_call=tool_call,
            checks=checks,
            passed=False,
            notes="arguments not an object",
        )

    declared = contract.declared_params()
    extra = set(arguments) - declared
    no_forbidden = not extra and not (set(question.forbidden_params) & set(arguments))
    retry_params_correct = all(
        name in arguments
        and normalize_value(arguments[name]) == normalize_value(expected)
        for name, expected in question.expected_retry_params.items()
    )
    checks = RecoveryChecks(
        single_tool=True,
        error_identified=_error_identified(content),
        retry_params_correct=retry_params_correct,
        no_forbidden=no_forbidden,
    )
    return RecoveryResult(
        question_id=question.question_id,
        round=0,
        model="",
        content=content,
        tool_call=tool_call,
        checks=checks,
        passed=checks.passed(),
        notes=note,
    )


def run_recovery_probe(
    contract: ToolContract,
    questions: tuple[RecoveryQuestion, ...],
    llm_fn: Callable[[RecoveryQuestion, ToolContract], dict[str, Any]],
    *,
    rounds: int = 2,
    model: str = "deepseek-v4-flash",
) -> list[RecoveryResult]:
    """Run one fixed failure-recovery question for N rounds."""
    results: list[RecoveryResult] = []
    for question in questions:
        for round_index in range(1, rounds + 1):
            message = llm_fn(question, contract)
            result = evaluate_recovery(contract, question, message)
            results.append(
                RecoveryResult(
                    question_id=result.question_id,
                    round=round_index,
                    model=model,
                    content=result.content,
                    tool_call=result.tool_call,
                    checks=result.checks,
                    passed=result.passed,
                    notes=result.notes,
                    difficulty=question.difficulty,
                    provider_id=contract.provider_id,
                    access_path_id=contract.access_path_id,
                )
            )
    return results
