#!/usr/bin/env python3
"""Run the agent error-recovery probe: read a failed response and retry."""

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

from qveris_bench.agent_trial.error_recovery import (
    RecoveryQuestion,
    RecoveryResult,
    run_recovery_probe,
)
from qveris_bench.agent_trial.param_fill import ParamSpec, ToolContract
from qveris_bench.providers.repository import ProviderRegistryRepository

_BASE_URL_ENV = "QVERIS_MODEL_BASE_URL"
_API_KEY_ENV = "QVERIS_MODEL_API_KEY"
_MODEL_ENV = "QVERIS_MODEL_NAME"
_DEFAULT_BASE_URL = "https://aigateway.qveris.ai/v1"
_DEFAULT_MODEL = "deepseek-v4-flash"


def load_fixture(
    path: Path,
    providers_root: Path | None = None,
) -> tuple[tuple[ToolContract, tuple[RecoveryQuestion, ...]], ...]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    probes: list[tuple[ToolContract, tuple[RecoveryQuestion, ...]]] = []
    for tool_doc in document["tools"]:
        contract = ToolContract(
            tool_id=tool_doc["tool_id"],
            name=tool_doc["name"],
            description=tool_doc["description"],
            provider_id=tool_doc["provider_id"],
            access_path_id=tool_doc["access_path_id"],
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
            RecoveryQuestion(
                question_id=case["question_id"],
                task=case["task"],
                failure_response=case["failure_response"],
                expected_retry_params=dict(case.get("expected_retry_params", {})),
                forbidden_params=tuple(case.get("forbidden_params", ())),
                difficulty=case.get("difficulty", "L2"),
            )
            for case in tool_doc["cases"]
        )
        probes.append((contract, questions))
    loaded = tuple(probes)
    if providers_root is not None:
        ProviderRegistryRepository(providers_root).validate_access_path_identities(
            (contract.provider_id, contract.access_path_id) for contract, _ in loaded
        )
    return loaded


def build_llm_fn(
    base_url: str, key: str, model: str
) -> Callable[[RecoveryQuestion, ToolContract], dict[str, Any]]:
    def llm_fn(question: RecoveryQuestion, contract: ToolContract) -> dict[str, Any]:
        payload = {
            "model": model,
            "temperature": 0,
            "tools": [contract.to_openai_tool()],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "A tool call failed and returned the response below. "
                        "Briefly explain why it failed in one sentence, then retry "
                        "the SAME tool with corrected parameters. Do not invent "
                        "parameters that the tool schema does not declare."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{question.task}\n\n"
                        f"Failed tool response:\n{question.failure_response}"
                    ),
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
        message = (body.get("choices") or [{}])[0].get("message") or {}
        return message

    return llm_fn


def _result_record(result: RecoveryResult, at: str) -> dict[str, Any]:
    return {
        "provider_id": result.provider_id,
        "access_path_id": result.access_path_id,
        "question_id": result.question_id,
        "round": result.round,
        "model": result.model,
        "passed": result.passed,
        "checks": {
            "single_tool": result.checks.single_tool,
            "error_identified": result.checks.error_identified,
            "retry_params_correct": result.checks.retry_params_correct,
            "no_forbidden": result.checks.no_forbidden,
        },
        "notes": result.notes,
        "difficulty": result.difficulty,
        "content": result.content,
        "tool_call": result.tool_call,
        "recorded_at": at,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("scripts/fixtures/agent-error-recovery-fx.yaml"),
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
        default=Path("evidence/private/agent-error-recovery.jsonl"),
    )
    args = parser.parse_args(argv)

    key = os.getenv(_API_KEY_ENV)
    if not key:
        print(f"{_API_KEY_ENV} is required.", file=sys.stderr)
        return 2

    llm_fn = build_llm_fn(args.base_url.rstrip("/"), key, args.model)
    results: list[RecoveryResult] = []
    for contract, questions in load_fixture(args.fixture, Path("providers")):
        results.extend(
            run_recovery_probe(
                contract,
                questions,
                llm_fn,
                rounds=args.rounds,
                model=args.model,
            )
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
            f"  {result.question_id} round={result.round} passed={result.passed} "
            f"checks={result.checks}"
        )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
