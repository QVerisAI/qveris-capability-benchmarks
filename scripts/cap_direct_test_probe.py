#!/usr/bin/env python3
"""Run our own CAP Direct Test: fixed cases through QVeris, contract-driven rules."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from qveris_bench.providers.repository import ProviderRegistryRepository


@dataclass(frozen=True)
class Case:
    case_id: str
    parameters: dict[str, Any]
    expected_observations: tuple[str, ...]
    negative_control: bool


@dataclass(frozen=True)
class SupplierProbe:
    supplier: str
    provider_id: str
    access_path_id: str
    tool_id: str
    cases: tuple[Case, ...]


@dataclass(frozen=True)
class CellResult:
    supplier: str
    case_id: str
    round: int
    state: str
    provider_id: str = ""
    access_path_id: str = ""
    missing: tuple[str, ...] = ()
    notes: str = ""
    latency_ms: float | None = None
    cost_credits: float | None = None


def _observation_present(data: Any, observation: str) -> bool:
    if isinstance(data, dict):
        if observation not in data:
            return False
        value = data[observation]
        return value is not None and value != "" and value != []
    if isinstance(data, str):
        lines = [line for line in data.strip().splitlines() if line.strip()]
        if len(lines) < 2:
            return False
        header = " ".join(lines[0].lower().split())
        return observation.lower().replace("_", " ") in header
    if isinstance(data, list):
        return bool(data)
    return False


def _negative_ok(data: Any, status_code: int) -> bool:
    if status_code not in (200, 204):
        return True
    if data is None:
        return True
    if isinstance(data, dict):
        return not _has_event_rows(data)
    if isinstance(data, list):
        return not data
    if isinstance(data, str):
        return len([line for line in data.strip().splitlines() if line.strip()]) < 2
    return True


def _has_event_rows(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return any(_has_event_rows(item) for item in value.values())
    return False


def load_fixture(
    path: Path, providers_root: Path | None = None
) -> tuple[SupplierProbe, ...]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    probes: list[SupplierProbe] = []
    for supplier_doc in document["suppliers"]:
        cases = tuple(
            Case(
                case_id=case["case_id"],
                parameters=case["parameters"],
                expected_observations=tuple(case.get("expected_observations", ())),
                negative_control=case.get("negative_control", False),
            )
            for case in supplier_doc["cases"]
        )
        probes.append(
            SupplierProbe(
                supplier=supplier_doc["supplier"],
                provider_id=supplier_doc["provider_id"],
                access_path_id=supplier_doc["access_path_id"],
                tool_id=supplier_doc["tool_id"],
                cases=cases,
            )
        )
    loaded = tuple(probes)
    if providers_root is not None:
        ProviderRegistryRepository(providers_root).validate_access_path_identities(
            (probe.provider_id, probe.access_path_id) for probe in loaded
        )
    return loaded


def build_executor(
    base_url: str, api_key: str
) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    search_ids: dict[str, str] = {}

    def execute(tool_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
        search_id = search_ids.get(tool_id)
        if search_id is None:
            search_request = urllib.request.Request(
                f"{base_url}/search",
                data=json.dumps({"query": tool_id, "limit": 1}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(search_request, timeout=90) as response:
                    search_id = json.loads(response.read().decode("utf-8"))["search_id"]
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"search HTTP {exc.code}") from exc
            search_ids[tool_id] = search_id
        execute_request = urllib.request.Request(
            f"{base_url}/tools/execute?tool_id={urllib.parse.quote(tool_id)}",
            data=json.dumps({"search_id": search_id, "parameters": parameters}).encode(
                "utf-8"
            ),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(execute_request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"execute HTTP {exc.code}") from exc
        result = body.get("result") or {}
        billing = body.get("billing") or {}
        return {
            "status_code": result.get("status_code"),
            "data": result.get("data"),
            "latency_ms": body.get("elapsed_time_ms"),
            "cost_credits": billing.get("list_amount_credits"),
        }

    return execute


def evaluate_cell(case: Case, outcome: dict[str, Any]) -> CellResult:
    data = outcome.get("data")
    status_code = outcome.get("status_code")
    if status_code is None:
        return CellResult(
            "",
            case.case_id,
            0,
            "n_a",
            notes="no execution result",
            latency_ms=outcome.get("latency_ms"),
            cost_credits=outcome.get("cost_credits"),
        )
    if case.negative_control:
        passed = _negative_ok(data, status_code)
        return CellResult(
            "",
            case.case_id,
            0,
            "passed" if passed else "failed",
            notes=("" if passed else "negative control returned data"),
            latency_ms=outcome.get("latency_ms"),
            cost_credits=outcome.get("cost_credits"),
        )
    missing = tuple(
        observation
        for observation in case.expected_observations
        if not _observation_present(data, observation)
    )
    state = "passed" if not missing else "failed"
    return CellResult(
        "",
        case.case_id,
        0,
        state,
        missing=missing,
        latency_ms=outcome.get("latency_ms"),
        cost_credits=outcome.get("cost_credits"),
    )


def run_probe(
    probes: tuple[SupplierProbe, ...],
    execute: Callable[[str, dict[str, Any]], dict[str, Any]],
    *,
    rounds: int = 2,
) -> list[CellResult]:
    def run_supplier(probe: SupplierProbe) -> list[CellResult]:
        results: list[CellResult] = []
        for case in probe.cases:
            for round_index in range(1, rounds + 1):
                try:
                    outcome = execute(probe.tool_id, case.parameters)
                    result = evaluate_cell(case, outcome)
                except (RuntimeError, TimeoutError) as exc:
                    result = CellResult(
                        probe.supplier,
                        case.case_id,
                        round_index,
                        "n_a",
                        provider_id=probe.provider_id,
                        access_path_id=probe.access_path_id,
                        notes=str(exc),
                    )
                results.append(
                    CellResult(
                        probe.supplier,
                        case.case_id,
                        round_index,
                        result.state,
                        provider_id=probe.provider_id,
                        access_path_id=probe.access_path_id,
                        missing=result.missing,
                        notes=result.notes,
                        latency_ms=result.latency_ms,
                        cost_credits=result.cost_credits,
                    )
                )
        return results

    with ThreadPoolExecutor(max_workers=len(probes)) as pool:
        return [
            result for results in pool.map(run_supplier, probes) for result in results
        ]


def probe_state(cells: list[CellResult]) -> str:
    if any(cell.state == "failed" for cell in cells):
        return "failed"
    if not cells or any(cell.state == "n_a" for cell in cells):
        return "n_a"
    return "passed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("scripts/fixtures/cap-direct-test-corporate-actions.yaml"),
    )
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--base-url", default="https://qveris.ai/api/v1")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/private/cap-direct-test.jsonl"),
    )
    args = parser.parse_args(argv)

    api_key = os.getenv("QVERIS_API_KEY")
    if not api_key:
        print("QVERIS_API_KEY is required.", file=sys.stderr)
        return 2

    probes = load_fixture(args.fixture, Path("providers"))
    execute = build_executor(args.base_url.rstrip("/"), api_key)
    results = run_probe(probes, execute, rounds=args.rounds)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).isoformat()
    with args.output.open("a", encoding="utf-8") as handle:
        for result in results:
            handle.write(
                json.dumps(
                    {
                        "supplier": result.supplier,
                        "provider_id": result.provider_id,
                        "access_path_id": result.access_path_id,
                        "case_id": result.case_id,
                        "round": result.round,
                        "state": result.state,
                        "missing": list(result.missing),
                        "notes": result.notes,
                        "latency_ms": result.latency_ms,
                        "cost_credits": result.cost_credits,
                        "recorded_at": recorded_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    exit_code = 0
    for probe in probes:
        cells = [
            result
            for result in results
            if result.provider_id == probe.provider_id
            and result.access_path_id == probe.access_path_id
        ]
        failed = [result for result in cells if result.state == "failed"]
        state = probe_state(cells)
        if state != "passed":
            exit_code = 1
        display_state = {
            "passed": "合格",
            "failed": "未完全达标",
            "n_a": "n_a",
        }[state]
        latencies = [
            result.latency_ms for result in cells if result.latency_ms is not None
        ]
        costs = [
            result.cost_credits for result in cells if result.cost_credits is not None
        ]
        avg_latency = (
            f"{sum(latencies) / len(latencies):.0f}ms" if latencies else "无样本"
        )
        avg_cost = f"{sum(costs) / len(costs):.2f} credits" if costs else "无样本"
        print(
            f"{probe.supplier}: {display_state} "
            f"({len(cells)} cells, failed={len(failed)}, "
            f"latency={avg_latency}, cost={avg_cost})"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
