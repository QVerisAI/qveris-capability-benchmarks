"""Agent response-interpretation evaluation for tool outputs."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_TICKER_RE = re.compile(r"\b[A-Z]{2,6}\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{10}\b")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_NO_DATA_WORDS = (
    "no data",
    "no result",
    "not found",
    "invalid",
    "error",
    "empty",
    "无数据",
    "无效",
    "未找到",
    "没有",
)


@dataclass(frozen=True)
class InterpretationQuestion:
    question_id: str
    task: str
    expected_values: dict[str, Any] = field(default_factory=dict)
    unit_fields: tuple[tuple[str, str], ...] = ()
    negative_control: bool = False
    require_timestamp: bool = False


@dataclass(frozen=True)
class InterpretationChecks:
    extraction_correct: bool
    no_hallucination: bool
    unit_semantics: bool
    negative_state: bool
    as_of_used: bool

    def passed(self) -> bool:
        return all(
            (
                self.extraction_correct,
                self.no_hallucination,
                self.unit_semantics,
                self.negative_state,
                self.as_of_used,
            )
        )


@dataclass(frozen=True)
class InterpretationResult:
    question_id: str
    round: int
    model: str
    answer: str
    checks: InterpretationChecks
    passed: bool
    notes: str = ""


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number_tokens(text: str) -> list[float]:
    return [float(token) for token in re.findall(r"-?\d+(?:\.\d+)?", text)]


def _contains_value(answer: str, expected: Any) -> bool:
    if _is_number(expected):
        target = float(expected)
        return any(
            abs(token - target) <= max(abs(target) * 0.02, 0.01)
            for token in _number_tokens(answer)
        )
    normalized = str(expected).strip().upper()
    if normalized in answer.upper():
        return True
    date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(expected))
    if date_match:
        year, month, day = date_match.groups()
        return any(
            variant in answer
            for variant in (
                f"{year}年{int(month)}月{int(day)}日",
                f"{year}/{month}/{day}",
                f"{int(month)}/{int(day)}/{year}",
            )
        )
    return False


def _unit_in_answer(answer: str, unit_token: str) -> bool:
    normalized = unit_token.lower()
    if normalized in answer.lower():
        return True
    if normalized == "usd":
        return "美元" in answer
    return False


def _has_no_data_signal(answer: str) -> bool:
    lowered = answer.lower()
    return any(word in lowered for word in _NO_DATA_WORDS)


def _has_number(answer: str) -> bool:
    """Any numeric token, including integers, counts as a fabricated value."""
    return bool(_NUMBER_RE.search(answer))


def evaluate_interpretation(
    question: InterpretationQuestion,
    response_text: str,
    answer: str,
) -> InterpretationChecks:
    extraction_correct = all(
        _contains_value(answer, expected)
        for expected in question.expected_values.values()
    )
    response_tickers = set(_TICKER_RE.findall(response_text.upper()))
    answer_tickers = set(_TICKER_RE.findall(answer.upper()))
    response_dates = set(_DATE_RE.findall(response_text))
    answer_dates = set(_DATE_RE.findall(answer))
    no_hallucination = (
        answer_tickers <= response_tickers and answer_dates <= response_dates
    )
    unit_semantics = (
        question.negative_control
        or not question.unit_fields
        or all(_unit_in_answer(answer, unit) for _, unit in question.unit_fields)
    )
    negative_state = not question.negative_control or (
        _has_no_data_signal(answer) and not _has_number(answer)
    )
    as_of_used = not question.require_timestamp or bool(
        answer_dates & response_dates
        or any(token in answer for token in response_dates)
    )
    return InterpretationChecks(
        extraction_correct=extraction_correct,
        no_hallucination=no_hallucination,
        unit_semantics=unit_semantics,
        negative_state=negative_state,
        as_of_used=as_of_used,
    )


def run_interpretation_probe(
    questions: tuple[InterpretationQuestion, ...],
    response_texts: dict[str, str],
    llm_fn: Callable[[InterpretationQuestion, str], str],
    *,
    rounds: int = 2,
    model: str = "deepseek-v4-flash",
) -> list[InterpretationResult]:
    results: list[InterpretationResult] = []
    for question in questions:
        response_text = response_texts[question.question_id]
        for round_index in range(1, rounds + 1):
            answer = llm_fn(question, response_text)
            checks = evaluate_interpretation(question, response_text, answer)
            results.append(
                InterpretationResult(
                    question_id=question.question_id,
                    round=round_index,
                    model=model,
                    answer=answer,
                    checks=checks,
                    passed=checks.passed(),
                )
            )
    return results
