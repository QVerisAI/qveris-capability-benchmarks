#!/usr/bin/env python3
# ruff: noqa: E501  # generated YAML content lines legitimately exceed 88 cols
"""Generate probe fixture skeletons from a Harbor CAP contract.

Reads the Harbor explore v2 contract export (contracts.json) and derives the
five probe fixture skeletons for one CAP:
  - cap-direct-test-<cap>.yaml
  - agent-param-fill-<cap>.yaml
  - agent-response-interpretation-<cap>.yaml
  - agent-error-recovery-<cap>.yaml
  - <cap>-response-self-description.yaml

The contract's standard_query / field_spec / row_key drive the skeleton's
shape: required standard_query fields mark the query inputs, field_spec
required fields mark the expected observations, and row_key picks the
self-description elements. Concrete tool bindings (tool_id / provider_id /
access_path_id) and real query parameters are NOT derivable from the contract
alone -- provider tools use their own parameter names (e.g. EODHD "from/to"
vs TwelveData "start_date/end_date"). The generator therefore emits these as
explicit TODO placeholders so a human fills the provider-specific mapping;
it never fabricates a value into a comparison field.

Usage:
    uv run python scripts/generate_cap_fixtures.py \
        --contracts /tmp/harbor-cat/contracts.json \
        --cap MKT.DIVIDENDS --cap-slug dividends \
        --output scripts/fixtures/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def load_contracts(contracts_path: Path) -> dict[str, dict[str, Any]]:
    records = json.loads(contracts_path.read_text(encoding="utf-8"))
    return {record["capability_id"]: record["contract"] for record in records}


def _required_names(fields: Any) -> list[str]:
    """Extract required field names from a standard_query / field_spec mapping."""
    if not isinstance(fields, dict):
        return []
    names: list[str] = []
    for field in fields.get("required", []) or []:
        name = field.get("name") if isinstance(field, dict) else None
        if name:
            names.append(name)
    return names


def _field_info(fields: Any, name: str) -> dict[str, Any] | None:
    """Return the field spec entry for a given name."""
    if not isinstance(fields, dict):
        return None
    for group in ("required", "optional"):
        for field in fields.get(group, []) or []:
            if isinstance(field, dict) and field.get("name") == name:
                return field
    return None


def _validate_contract(contract: dict[str, Any]) -> list[str]:
    """Return the list of missing sections a renderer needs (empty = OK)."""
    missing: list[str] = []
    if not contract.get("standard_query"):
        missing.append("standard_query")
    if not contract.get("field_spec"):
        missing.append("field_spec")
    if not contract.get("row_key"):
        missing.append("row_key")
    return missing


def _todo_params(names: list[str]) -> str:
    """Emit expected_params as a JSON mapping of contract fields to TODO markers."""
    return json.dumps({n: "<TODO>" for n in names}, ensure_ascii=False)


def render_param_fill(contract: dict[str, Any], cap_slug: str) -> str:
    standard_query = contract.get("standard_query", {})
    required = _required_names(standard_query)
    rows: list[str] = ["tools:"]
    for field in standard_query.get("required", []) or []:
        name = field.get("name", "field")
        ftype = field.get("type", "string")
        rows.append(f"  - tool_id: <TODO tool_id_for_{name}>")
        rows.append("    provider_id: <TODO provider_id>")
        rows.append("    access_path_id: <TODO access_path_id>")
        rows.append("    name: <TODO tool display name>")
        rows.append("    description: <TODO tool description>")
        rows.append("    params:")
        rows.append(
            f'      - {{name: <TODO provider_param_for_{name}>, type: {ftype}, required: true, description: "{name}"}}'
        )
        rows.append("    questions:")
        rows.append(f"      - question_id: {cap_slug}-{name}-core")
        rows.append("        task: <!-- TODO 用自然语言描述查询任务 -->")
        rows.append(f"        expected_params: {_todo_params(required)}")
        rows.append("        difficulty: L2")
    return "\n".join(rows)


def render_direct_test(contract: dict[str, Any], cap_slug: str) -> str:
    standard_query = contract.get("standard_query", {})
    field_spec = contract.get("field_spec", {})
    query_required = _required_names(standard_query)
    expected = _required_names(field_spec)
    rows: list[str] = [f"capability: {contract.get('capability_id', '')}", "suppliers:"]
    if query_required:
        first = query_required[0]
        rows.append(f"  - supplier: <TODO supplier_for_{first}>")
        rows.append("    provider_id: <TODO provider_id>")
        rows.append("    access_path_id: <TODO access_path_id>")
        rows.append(f"    tool_id: <TODO tool_id_for_{first}>")
        rows.append("    cases:")
        rows.append(
            f"      - {{case_id: {cap_slug}-positive, parameters: <TODO provider_query_params>, expected_observations: {json.dumps(expected, ensure_ascii=False)}, negative_control: false}}"
        )
        rows.append(
            f"      - {{case_id: invalid-{first}, parameters: <TODO invalid_{first}>, expected_observations: [], negative_control: true}}"
        )
    else:
        rows.append("    # <!-- TODO 需要人工补充供应商与用例 -->")
    return "\n".join(rows)


def render_interpretation(contract: dict[str, Any], cap_slug: str) -> str:
    field_spec = contract.get("field_spec", {})
    required = _required_names(field_spec)
    number_fields = [
        f.get("name")
        for f in field_spec.get("required", []) or []
        if isinstance(f, dict) and f.get("type") in ("number", "integer", "float")
    ]
    rows: list[str] = ["cases:"]
    rows.append(f"  - question_id: {cap_slug}-positive")
    rows.append("    task: <!-- TODO 描述查询任务，只使用工具响应中的数据 -->")
    rows.append("    response_text: '<TODO 冻结的真实响应>'")
    rows.append(f"    expected_values: {_todo_params(required)}")
    if number_fields:
        rows.append(f"    unit_fields: [[{number_fields[0]}, <TODO unit>]]")
    else:
        rows.append("    unit_fields: []")
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
    rows: list[str] = ["tools:"]
    if required:
        rows.append(f"  - tool_id: <TODO tool_id_for_{required[0]}>")
        rows.append("    provider_id: <TODO provider_id>")
        rows.append("    access_path_id: <TODO access_path_id>")
        rows.append("    name: <TODO tool display name>")
        rows.append("    description: <TODO tool description>")
        rows.append("    params:")
        rows.append(
            f'      - {{name: <TODO provider_param_for_{required[0]}>, type: string, required: true, description: "{required[0]}"}}'
        )
        rows.append("    cases:")
        rows.append(f"      - question_id: {cap_slug}-recovery")
        rows.append("        task: <!-- TODO 描述查询任务 -->")
        rows.append("        failure_response: '<TODO 冻结的真实失败响应>'")
        rows.append(f"        expected_retry_params: {_todo_params(required)}")
        rows.append("        difficulty: L2")
    else:
        rows.append("    # <!-- TODO 需要人工补充工具与用例 -->")
    return "\n".join(rows)


def render_self_description(contract: dict[str, Any], cap_slug: str) -> str:
    row_key = contract.get("row_key", [])
    field_spec = contract.get("field_spec", {})
    elements: list[str] = list(row_key) if isinstance(row_key, list) else []
    # Append a numeric field as the value element when row_key has no value.
    number_fields = [
        name
        for f in field_spec.get("required", []) or []
        if isinstance(f, dict)
        and f.get("type") in ("number", "integer", "float")
        and isinstance((name := f.get("name")), str)
    ]
    if number_fields and number_fields[0] not in elements:
        elements.append(number_fields[0])
    if not elements:
        elements = ["<TODO element_id>"]
    rows: list[str] = [
        f"capability: {contract.get('capability_id', '')}",
        'edition: "2026-08-11"',
        "elements:",
    ]
    for element in elements:
        rows.append(f"  - {{id: {element}, label: <TODO 中文语义名>}}")
    rows.append("cases:")
    rows.append("  - supplier: <TODO supplier>")
    rows.append("    provider_id: <TODO provider_id>")
    rows.append("    access_path_id: <TODO access_path_id>")
    rows.append("    response_text: '<TODO 冻结的真实响应>'")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--cap", required=True)
    parser.add_argument("--cap-slug", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.contracts.exists():
        print(f"错误: contracts 文件不存在: {args.contracts}", file=sys.stderr)
        return 1

    contracts = load_contracts(args.contracts)
    if args.cap not in contracts:
        print(f"错误: CAP 不存在: {args.cap}", file=sys.stderr)
        return 1
    contract = contracts[args.cap]

    missing = _validate_contract(contract)
    if missing:
        print(
            f"错误: CAP {args.cap} 缺少生成所需契约段: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

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

    # Validate every emitted fixture parses as YAML before writing any file.
    for name, content in renders.items():
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            print(f"错误: 生成 {name} 的 YAML 非法: {exc}", file=sys.stderr)
            return 1

    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in renders.items():
        (args.output / name).write_text(content + "\n", encoding="utf-8")
        print(f"written: {args.output / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
