#!/usr/bin/env python3
"""Probe whether the AI can determine response semantics from the response alone."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

_BASE_URL_ENV = "QVERIS_MODEL_BASE_URL"
_API_KEY_ENV = "QVERIS_MODEL_API_KEY"
_MODEL_ENV = "QVERIS_MODEL_NAME"
_DEFAULT_BASE_URL = "https://aigateway.qveris.ai/v1"
_DEFAULT_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class SelfDescriptionCase:
    supplier: str
    response_text: str


@dataclass(frozen=True)
class ElementResult:
    supplier: str
    element: str
    round: int
    determined: bool
    answer: str


def load_fixture(
    path: Path,
) -> tuple[tuple[tuple[str, str], ...], tuple[SelfDescriptionCase, ...]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    elements = tuple((item["id"], item["label"]) for item in document["elements"])
    cases = tuple(
        SelfDescriptionCase(
            supplier=case["supplier"],
            response_text=case["response_text"],
        )
        for case in document["cases"]
    )
    return elements, cases


def build_llm_fn(base_url: str, key: str, model: str):
    def llm_fn(question: str) -> str:
        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
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


def _question(response_text: str, label: str) -> str:
    return (
        f"仅凭下面这个工具响应，你能确定它的【{label}】吗？"
        "只能回答：能 或 不能。不能时请用一句话说明缺了什么字段。\n\n"
        f"工具响应：{response_text}"
    )


def _determined(answer: str) -> bool:
    return answer.strip().startswith("能")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("scripts/fixtures/fx-response-self-description.yaml"),
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
        default=Path("evidence/private/agent-response-self-description.jsonl"),
    )
    args = parser.parse_args(argv)

    key = os.getenv(_API_KEY_ENV)
    if not key:
        print(f"{_API_KEY_ENV} is required.", file=sys.stderr)
        return 2

    elements, cases = load_fixture(args.fixture)
    llm_fn = build_llm_fn(args.base_url.rstrip("/"), key, args.model)

    results: list[ElementResult] = []
    for case in cases:
        for element, label in elements:
            for round_index in range(1, args.rounds + 1):
                answer = llm_fn(_question(case.response_text, label))
                results.append(
                    ElementResult(
                        supplier=case.supplier,
                        element=element,
                        round=round_index,
                        determined=_determined(answer),
                        answer=answer,
                    )
                )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).isoformat()
    with args.output.open("a", encoding="utf-8") as handle:
        for result in results:
            handle.write(
                json.dumps(
                    {
                        "supplier": result.supplier,
                        "element": result.element,
                        "round": result.round,
                        "determined": result.determined,
                        "answer": result.answer,
                        "recorded_at": recorded_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    for supplier in {result.supplier for result in results}:
        cells = [result for result in results if result.supplier == supplier]
        ok = sum(1 for result in cells if result.determined)
        print(f"{supplier}: {ok}/{len(cells)} 可确定")
        for result in cells:
            print(
                f"  {result.element} r{result.round}: "
                f"{'能' if result.determined else '不能'} | {result.answer[:70]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
