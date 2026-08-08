#!/usr/bin/env python3
"""Run the agent parameter-fill probe against an OpenAI-compatible model gateway."""

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
from typing import Any

import yaml

from qveris_bench.agent_trial.param_fill import (
    AgentQuestion,
    ParamFillResult,
    ParamSpec,
    ToolContract,
    run_probe,
)

_BASE_URL_ENV = "QVERIS_MODEL_BASE_URL"
_API_KEY_ENV = "QVERIS_MODEL_API_KEY"
_MODEL_ENV = "QVERIS_MODEL_NAME"
_DEFAULT_BASE_URL = "https://aigateway.qveris.ai/v1"
_DEFAULT_MODEL = "deepseek-v4-flash"


def load_fixture(path: Path) -> tuple[ToolContract, tuple[AgentQuestion, ...]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    tool_doc = document["tool"]
    contract = ToolContract(
        tool_id=tool_doc["tool_id"],
        name=tool_doc["name"],
        description=tool_doc["description"],
        params=tuple(
            ParamSpec(
                name=param["name"],
                type=param["type"],
                required=param.get("required", False),
                description=param.get("description", ""),
            )
            for param in tool_doc["params"]
        ),
    )
    questions = tuple(
        AgentQuestion(
            question_id=question["question_id"],
            task=question["task"],
            expected_params=dict(question.get("expected_params", {})),
            forbidden_params=tuple(question.get("forbidden_params", ())),
        )
        for question in document["questions"]
    )
    return contract, questions


def build_llm_fn(
    base_url: str, api_key: str, model: str
) -> Callable[[AgentQuestion, ToolContract], dict[str, Any]]:
    def llm_fn(question: AgentQuestion, contract: ToolContract) -> dict[str, Any]:
        payload = {
            "model": model,
            "temperature": 0,
            "tools": [contract.to_openai_tool()],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You call exactly one tool with the parameters needed to "
                        "answer the user request. Do not invent parameters that the "
                        "tool schema does not declare."
                    ),
                },
                {"role": "user", "content": question.task},
            ],
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"model gateway HTTP {exc.code}: {exc.reason}") from exc
        message = (body.get("choices") or [{}])[0].get("message") or {}
        return message

    return llm_fn


def _result_record(result: ParamFillResult, at: str) -> dict[str, Any]:
    return {
        "question_id": result.question_id,
        "round": result.round,
        "model": result.model,
        "passed": result.passed,
        "checks": {
            "single_tool": result.checks.single_tool,
            "required_present": result.checks.required_present,
            "value_valid": result.checks.value_valid,
            "no_forbidden": result.checks.no_forbidden,
            "semantics_match": result.checks.semantics_match,
        },
        "notes": result.notes,
        "tool_call": result.tool_call,
        "recorded_at": at,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("scripts/fixtures/agent-param-fill-finnhub-quote.yaml"),
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
        default=Path("evidence/private/agent-param-fill.jsonl"),
    )
    args = parser.parse_args(argv)

    api_key = os.getenv(_API_KEY_ENV)
    if not api_key:
        print(f"{_API_KEY_ENV} is required.", file=sys.stderr)
        return 2

    contract, questions = load_fixture(args.fixture)
    llm_fn = build_llm_fn(args.base_url.rstrip("/"), api_key, args.model)
    results = run_probe(
        contract,
        questions,
        llm_fn,
        rounds=args.rounds,
        model=args.model,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).isoformat()
    with args.output.open("a", encoding="utf-8") as handle:
        for result in results:
            handle.write(
                json.dumps(_result_record(result, recorded_at), ensure_ascii=False)
                + "\n"
            )

    passed = sum(1 for result in results if result.passed)
    print(f"passed {passed}/{len(results)}")
    for result in results:
        print(
            f"  {result.question_id} round={result.round} "
            f"passed={result.passed} checks={result.checks}"
        )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
