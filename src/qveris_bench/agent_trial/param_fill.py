"""Agent parameter-fill evaluation for canonical tool calls."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


def _normalize(value: Any) -> str:
    if isinstance(value, list):
        return "|".join(str(item).strip().upper() for item in value)
    return str(value).strip().upper() if value is not None else ""


def sanitize_tool_name(tool_id: str) -> str:
    """LLM gateways restrict function names to [a-zA-Z0-9_-]."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", tool_id)


@dataclass(frozen=True)
class ParamSpec:
    name: str
    type: str
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class ToolContract:
    tool_id: str
    name: str
    description: str
    params: tuple[ParamSpec, ...] = ()

    def to_openai_tool(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param in self.params:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
        return {
            "type": "function",
            "function": {
                "name": sanitize_tool_name(self.tool_id),
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def declared_params(self) -> set[str]:
        return {param.name for param in self.params}


@dataclass(frozen=True)
class AgentQuestion:
    question_id: str
    task: str
    expected_params: dict[str, str] = field(default_factory=dict)
    forbidden_params: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParamFillChecks:
    single_tool: bool
    required_present: bool
    value_valid: bool
    no_forbidden: bool
    semantics_match: bool

    def passed(self) -> bool:
        return all(
            (
                self.single_tool,
                self.required_present,
                self.value_valid,
                self.no_forbidden,
                self.semantics_match,
            )
        )


@dataclass(frozen=True)
class ParamFillResult:
    question_id: str
    round: int
    model: str
    tool_call: dict[str, Any] | None
    checks: ParamFillChecks
    passed: bool
    notes: str = ""


def _type_valid(param: ParamSpec, value: Any) -> bool:
    if param.type == "string":
        return isinstance(value, str) and bool(value.strip())
    if param.type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if param.type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if param.type == "boolean":
        return isinstance(value, bool)
    if param.type == "array":
        return isinstance(value, list)
    if param.type == "object":
        return isinstance(value, dict)
    return True


def _extract_tool_call(message: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None, "no tool call"
    if len(tool_calls) > 1:
        return None, "multiple tool calls"
    return tool_calls[0], ""


def evaluate_tool_call(
    contract: ToolContract,
    question: AgentQuestion,
    message: dict[str, Any],
) -> ParamFillResult:
    """Return per-check results for one model message against the tool contract."""
    tool_call, note = _extract_tool_call(message)
    checks = ParamFillChecks(
        single_tool=False,
        required_present=False,
        value_valid=False,
        no_forbidden=False,
        semantics_match=False,
    )
    if tool_call is None:
        return ParamFillResult(
            question_id=question.question_id,
            round=0,
            model="",
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
        return ParamFillResult(
            question_id=question.question_id,
            round=0,
            model="",
            tool_call=tool_call,
            checks=checks,
            passed=False,
            notes=f"wrong tool: {function.get('name')}",
        )
    checks = ParamFillChecks(
        single_tool=True,
        required_present=False,
        value_valid=False,
        no_forbidden=False,
        semantics_match=False,
    )
    try:
        arguments = json.loads(function.get("arguments") or "{}")
    except json.JSONDecodeError:
        return ParamFillResult(
            question_id=question.question_id,
            round=0,
            model="",
            tool_call=tool_call,
            checks=checks,
            passed=False,
            notes="malformed arguments",
        )
    if not isinstance(arguments, dict):
        return ParamFillResult(
            question_id=question.question_id,
            round=0,
            model="",
            tool_call=tool_call,
            checks=checks,
            passed=False,
            notes="arguments not an object",
        )

    required_present = all(
        param.required
        and param.name in arguments
        and arguments[param.name] not in (None, "")
        for param in contract.params
        if param.required
    )
    declared = contract.declared_params()
    extra = set(arguments) - declared
    no_forbidden = not extra and not (
        set(question.forbidden_params) & set(arguments)
    )
    value_valid = all(
        _type_valid(param, arguments[param.name])
        for param in contract.params
        if param.name in arguments
    )
    semantics_match = all(
        name in arguments and _normalize(arguments[name]) == _normalize(expected)
        for name, expected in question.expected_params.items()
    )
    checks = ParamFillChecks(
        single_tool=True,
        required_present=required_present,
        value_valid=value_valid,
        no_forbidden=no_forbidden,
        semantics_match=semantics_match,
    )
    return ParamFillResult(
        question_id=question.question_id,
        round=0,
        model="",
        tool_call=tool_call,
        checks=checks,
        passed=checks.passed(),
        notes=note,
    )


def run_probe(
    contract: ToolContract,
    questions: tuple[AgentQuestion, ...],
    llm_fn: Callable[[AgentQuestion, ToolContract], dict[str, Any]],
    *,
    rounds: int = 2,
    model: str = "deepseek-v4-flash",
) -> list[ParamFillResult]:
    """Run one fixed-question probe for N rounds and return per-round results."""
    results: list[ParamFillResult] = []
    for question in questions:
        for round_index in range(1, rounds + 1):
            message = llm_fn(question, contract)
            result = evaluate_tool_call(contract, question, message)
            results.append(
                ParamFillResult(
                    question_id=result.question_id,
                    round=round_index,
                    model=model,
                    tool_call=result.tool_call,
                    checks=result.checks,
                    passed=result.passed,
                    notes=result.notes,
                )
            )
    return results
