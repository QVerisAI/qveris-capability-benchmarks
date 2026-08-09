#!/usr/bin/env python3
"""Run the agent response-interpretation probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from qveris_bench.agent_trial.response_interpretation import (
    InterpretationQuestion,
    run_interpretation_probe,
)

_BASE_URL_ENV = "QVERIS_MODEL_BASE_URL"
_API_KEY_ENV = "QVERIS_MODEL_API_KEY"
_MODEL_ENV = "QVERIS_MODEL_NAME"
_DEFAULT_BASE_URL = "https://aigateway.qveris.ai/v1"
_DEFAULT_MODEL = "deepseek-v4-flash"


def load_fixture(path: Path) -> tuple[tuple[InterpretationQuestion, str], ...]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases: list[tuple[InterpretationQuestion, str]] = []
    for case in document["cases"]:
        question = InterpretationQuestion(
            question_id=case["question_id"],
            task=case["task"],
            expected_values=dict(case.get("expected_values", {})),
            unit_fields=tuple(tuple(item) for item in case.get("unit_fields", ())),
            negative_control=case.get("negative_control", False),
            require_timestamp=case.get("require_timestamp", False),
        )
        response = case["response_text"]
        cases.append((question, response))
    return tuple(cases)


def build_llm_fn(
    base_url: str, key: str, model: str
) -> Callable[[InterpretationQuestion, str], str]:
    def llm_fn(question: InterpretationQuestion, response_text: str) -> str:
        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Answer the user question using ONLY the tool response "
                        "provided. Do not add prices, dates, or symbols that are "
                        "not present in the response."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{question.task}\n\nTool response:\n{response_text}",
                },
            ],
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"model gateway HTTP {exc.code}: {exc.reason}") from exc
        return (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""

    return llm_fn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("scripts/fixtures/agent-response-interpretation-dividends.yaml"),
    )
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--model", default=os.getenv(_MODEL_ENV, _DEFAULT_MODEL))
    parser.add_argument(
        "--base-url",
        default=os.getenv(_BASE_URL_ENV, _DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/private/agent-response-interpretation.jsonl"),
    )
    args = parser.parse_args(argv)

    key = os.getenv(_API_KEY_ENV)
    if not key:
        print(f"{_API_KEY_ENV} is required.", file=sys.stderr)
        return 2

    cases = load_fixture(args.fixture)
    questions = tuple(question for question, _ in cases)
    response_texts = {question.question_id: response for question, response in cases}
    llm_fn = build_llm_fn(args.base_url.rstrip("/"), key, args.model)
    results = run_interpretation_probe(
        questions,
        response_texts,
        llm_fn,
        rounds=args.rounds,
        model=args.model,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).isoformat()
    with args.output.open("a", encoding="utf-8") as handle:
        for result in results:
            handle.write(
                json.dumps(
                    {
                        "question_id": result.question_id,
                        "round": result.round,
                        "model": result.model,
                        "passed": result.passed,
                        "checks": {
                            "extraction_correct": result.checks.extraction_correct,
                            "no_hallucination": result.checks.no_hallucination,
                            "unit_semantics": result.checks.unit_semantics,
                            "negative_state": result.checks.negative_state,
                            "as_of_used": result.checks.as_of_used,
                        },
                        "answer": result.answer,
                        "recorded_at": recorded_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    passed = sum(1 for result in results if result.passed)
    print(f"passed {passed}/{len(results)}")
    for result in results:
        print(
            f"  {result.question_id} round={result.round} passed={result.passed} "
            f"checks={result.checks}"
        )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
