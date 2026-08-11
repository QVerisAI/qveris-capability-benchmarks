#!/usr/bin/env python3
# ruff: noqa: E501  # generated YAML content lines legitimately exceed 88 cols
"""Generate probe fixture skeletons from a Harbor CAP contract.

Reads the Harbor explore v2 catalog export (catalog.json + contracts.json)
and derives the five probe fixture skeletons for one CAP:
  - cap-direct-test-<cap>.yaml
  - agent-param-fill-<cap>.yaml
  - agent-response-interpretation-<cap>.yaml
  - agent-error-recovery-<cap>.yaml
  - <cap>-response-self-description.yaml

Inputs (required params, expected fields, row key) come from the contract's
standard_query / field_spec / output_cardinality / row_key. Generated
fixtures are skeletons: tool_id / provider_id / access_path_id bindings and
frozen failure/response samples must be filled by a human or a probe run.

Usage:
    uv run python scripts/generate_cap_fixtures.py \
        --catalog /tmp/harbor-cat/catalog.json \
        --contracts /tmp/harbor-cat/contracts.json \
        --cap MKT.DIVIDENDS --cap-slug dividends \
        --output scripts/fixtures/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_contracts(contracts_path: Path) -> dict[str, dict[str, Any]]:
    records = json.loads(contracts_path.read_text(encoding="utf-8"))
    return {record["capability_id"]: record["contract"] for record in records}


def _field_names(fields: Any) -> list[str]:
    """Extract field names from a standard_query / field_spec mapping."""
    if not isinstance(fields, dict):
        return []
    names: list[str] = []
    for group in ("required", "optional"):
        for field in fields.get(group, []) or []:
            name = field.get("name") if isinstance(field, dict) else None
            if name:
                names.append(name)
    return names


def _required_names(fields: Any) -> list[str]:
    """Extract required field names only."""
    if not isinstance(fields, dict):
        return []
    names: list[str] = []
    for field in fields.get("required", []) or []:
        name = field.get("name") if isinstance(field, dict) else None
        if name:
            names.append(name)
    return names


def _sample_value(name: str, fields: Any) -> Any:
    """Pick a plausible sample value for a required field by its name."""
    samples = {
        "symbol": "AAPL",
        "effective_date": "2026-05-11",
        "start_date": "2024-01-01",
        "end_date": "2026-08-09",
        "ex_date": "2026-05-11",
        "from_currency": "EUR",
        "to_currency": "USD",
        "currency": "USD",
        "market": "US",
        "codes": "600519.SH",
        "stockObject": "600519.SH",
        "limit": 20,
    }
    if name in samples:
        return samples[name]
    # Fall back to a neutral string derived from the field name.
    return f"<{name}>"


def render_param_fill(contract: dict[str, Any], cap_slug: str) -> str:
    standard_query = contract.get("standard_query", {})
    required = _required_names(standard_query)
    rows: list[str] = ["tools:"]
    for field in standard_query.get("required", []) or []:
        name = field.get("name", "field")
        ftype = field.get("type", "string")
        desc = field.get("description", "")
        rows.append(f"  - tool_id: <tool_id_for_{name}>")
        rows.append("    provider_id: <provider_id>")
        rows.append("    access_path_id: <access_path_id>")
        rows.append("    name: <tool display name>")
        rows.append("    description: <tool description>")
        rows.append("    params:")
        rows.append(
            f'      - {{name: {name}, type: {ftype}, required: true, description: "{desc}"}}'
        )
        rows.append("    questions:")
        rows.append(f"      - question_id: {cap_slug}-{name}-core")
        rows.append("        task: <!-- TODO 用自然语言描述查询任务 -->")
        expected = {n: _sample_value(n, standard_query) for n in required[:2]}
        rows.append(
            f"        expected_params: {json.dumps(expected, ensure_ascii=False)}"
        )
        rows.append("        difficulty: L2")
    return "\n".join(rows)


def render_direct_test(contract: dict[str, Any], cap_slug: str) -> str:
    field_spec = contract.get("field_spec", {})
    required_fields = _required_names(field_spec)
    expected = required_fields[:3]
    rows: list[str] = [f"capability: {contract.get('capability_id', '')}", "suppliers:"]
    for name in required_fields[:1] or ["symbol"]:
        rows.append(f"  - supplier: <supplier_{name}>")
        rows.append("    provider_id: <provider_id>")
        rows.append("    access_path_id: <access_path_id>")
        rows.append(f"    tool_id: <tool_id_for_{name}>")
        rows.append("    cases:")
        params = {n: _sample_value(n, field_spec) for n in required_fields[:2]}
        rows.append(
            f"      - {{case_id: {cap_slug}-positive, parameters: {json.dumps(params, ensure_ascii=False)}, expected_observations: {json.dumps(expected, ensure_ascii=False)}, negative_control: false}}"
        )
        rows.append(
            "      - {case_id: invalid-symbol, parameters: {symbol: NOT_A_REAL_SYMBOL}, expected_observations: [], negative_control: true}"
        )
    return "\n".join(rows)


def render_interpretation(contract: dict[str, Any], cap_slug: str) -> str:
    field_spec = contract.get("field_spec", {})
    required = _required_names(field_spec)
    rows: list[str] = ["cases:"]
    rows.append(f"  - question_id: {cap_slug}-positive")
    rows.append("    task: <!-- TODO 描述查询任务，只使用工具响应中的数据 -->")
    rows.append("    response_text: '<TODO 冻结的真实响应>'")
    expected_values = {n: _sample_value(n, field_spec) for n in required[:2]}
    rows.append(
        f"    expected_values: {json.dumps(expected_values, ensure_ascii=False)}"
    )
    rows.append("    negative_control: false")
    rows.append("    require_timestamp: false")
    rows.append(f"  - question_id: {cap_slug}-negative")
    rows.append("    task: <!-- TODO 描述无效输入任务 -->")
    rows.append("    response_text: '<TODO 冻结的空态/错误响应>'")
    rows.append("    expected_values: {}")
    rows.append("    negative_control: true")
    rows.append("    require_timestamp: false")
    return "\n".join(rows)


def render_recovery(contract: dict[str, Any], cap_slug: str) -> str:
    standard_query = contract.get("standard_query", {})
    required = _required_names(standard_query)
    retry = {n: _sample_value(n, standard_query) for n in required[:2]}
    rows: list[str] = ["tools:"]
    for name in required[:1] or ["symbol"]:
        rows.append(f"  - tool_id: <tool_id_for_{name}>")
        rows.append("    provider_id: <provider_id>")
        rows.append("    access_path_id: <access_path_id>")
        rows.append("    name: <tool display name>")
        rows.append("    description: <tool description>")
        rows.append("    params:")
        rows.append(
            f'      - {{name: {name}, type: string, required: true, description: "{name}"}}'
        )
        rows.append("    cases:")
        rows.append(f"      - question_id: {cap_slug}-recovery")
        rows.append("        task: <!-- TODO 描述查询任务 -->")
        rows.append("        failure_response: '<TODO 冻结的真实失败响应>'")
        rows.append(
            f"        expected_retry_params: {json.dumps(retry, ensure_ascii=False)}"
        )
        rows.append("        difficulty: L2")
    return "\n".join(rows)


def render_self_description(contract: dict[str, Any], cap_slug: str) -> str:
    row_key = contract.get("row_key", [])
    elements = row_key[:3] if isinstance(row_key, list) else ["value", "unit", "time"]
    rows: list[str] = [
        f"capability: {contract.get('capability_id', '')}",
        'edition: "2026-08-11"',
        "elements:",
    ]
    for element in elements:
        rows.append(f"  - {{id: {element}, label: {element}}}")
    rows.append("cases:")
    for name in elements:
        rows.append(f"  - supplier: <supplier_{name}>")
        rows.append("    provider_id: <provider_id>")
        rows.append("    access_path_id: <access_path_id>")
        rows.append("    response_text: '<TODO 冻结的真实响应>'")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--cap", required=True)
    parser.add_argument("--cap-slug", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    contracts = load_contracts(args.contracts)
    if args.cap not in contracts:
        print(f"CAP 不存在: {args.cap}", file=__import__("sys").stderr)
        return 1
    contract = contracts[args.cap]

    renders = {
        f"cap-direct-test-{args.cap_slug}.yaml": render_direct_test(
            contract, args.cap_slug
        ),
        f"agent-param-fill-{args.cap_slug}.yaml": render_param_fill(
            contract, args.cap_slug
        ),
        f"agent-response-interpretation-{args.cap_slug}.yaml": render_interpretation(
            contract, args.cap_slug
        ),
        f"agent-error-recovery-{args.cap_slug}.yaml": render_recovery(
            contract, args.cap_slug
        ),
        f"{args.cap_slug}-response-self-description.yaml": render_self_description(
            contract, args.cap_slug
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in renders.items():
        (args.output / name).write_text(content + "\n", encoding="utf-8")
        print(f"written: {args.output / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
