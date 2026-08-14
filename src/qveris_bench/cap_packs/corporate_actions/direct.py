from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Any

from qveris_bench.execution.direct_binding import DirectBinding
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.releases.public_terminal import ValidatedTerminalOutcome


@dataclass(frozen=True)
class CorporateTerminal:
    state: CellState
    attribution: FailureAttribution | None
    facts: dict[str, object]


def evaluate(
    provider_id: str, case_id: str, payload: Mapping[str, Any]
) -> CorporateTerminal:
    if case_id == "invalid-corporate-actions-symbol":
        return _negative(provider_id, payload)
    if case_id != "aapl-splits-fixed-window":
        return _blocked(FailureAttribution.BENCHMARK_SYSTEM_ERROR)
    facts = _positive(provider_id, payload)
    return (
        CorporateTerminal(CellState.COMPLETED, None, facts)
        if facts is not None
        else _blocked(_transport_attribution(payload))
    )


def validate_public_outcome(
    case: BenchmarkCase, binding: DirectBinding, facts: dict[str, Any]
) -> ValidatedTerminalOutcome:
    if case.negative_control:
        if facts == {"validation_error": "provider_validation_error"}:
            return ValidatedTerminalOutcome(
                CellState.COMPLETED, (), FailureAttribution.PROVIDER_VALIDATION_ERROR
            )
        return ValidatedTerminalOutcome(
            CellState.PROVIDER_NEGATIVE,
            ("provider_validation_error",),
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    symbol = case.input.get("symbol")
    event_date = facts.get("date")
    if (
        facts.get("symbol") == symbol
        and facts.get("action_type") == "split"
        and isinstance(event_date, str)
        and _within_case_window(event_date, case)
    ):
        return ValidatedTerminalOutcome(CellState.COMPLETED, (), None)
    return ValidatedTerminalOutcome(
        CellState.INFRA_BLOCKED,
        ("symbol", "action_type", "date"),
        FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )


def _within_case_window(value: str, case: BenchmarkCase) -> bool:
    try:
        observed = date.fromisoformat(value)
        start = date.fromisoformat(str(case.input["start_date"]))
        end = date.fromisoformat(str(case.input["end_date"]))
    except (KeyError, TypeError, ValueError):
        return False
    return start <= observed <= end


def _positive(provider_id: str, payload: Mapping[str, Any]) -> dict[str, object] | None:
    data = payload.get("data")
    if payload.get("status_code") != 200:
        return None
    if provider_id == "eodhd" and isinstance(data, str):
        csv_rows = list(csv.DictReader(StringIO(data)))
        if csv_rows and isinstance(csv_rows[0].get("Date"), str):
            return {
                "symbol": "AAPL",
                "action_type": "split",
                "date": csv_rows[0]["Date"],
            }
    if provider_id == "twelve-data" and isinstance(data, Mapping):
        meta, splits = data.get("meta"), data.get("splits")
        if (
            isinstance(meta, Mapping)
            and meta.get("symbol") == "AAPL"
            and isinstance(splits, list)
        ):
            first = splits[0] if splits else None
            if isinstance(first, Mapping) and isinstance(first.get("date"), str):
                return {"symbol": "AAPL", "action_type": "split", "date": first["date"]}
    if provider_id == "alpha-vantage" and isinstance(data, Mapping):
        split_rows = data.get("data")
        if data.get("symbol") == "AAPL" and isinstance(split_rows, list):
            first = split_rows[0] if split_rows else None
            if isinstance(first, Mapping) and isinstance(
                first.get("effective_date"), str
            ):
                return {
                    "symbol": "AAPL",
                    "action_type": "split",
                    "date": first["effective_date"],
                }
    if provider_id == "massive-stocks" and isinstance(data, Mapping):
        split_rows = data.get("results")
        if isinstance(split_rows, list):
            first = split_rows[0] if split_rows else None
            if (
                isinstance(first, Mapping)
                and first.get("ticker") == "AAPL"
                and isinstance(first.get("execution_date"), str)
            ):
                return {
                    "symbol": "AAPL",
                    "action_type": "split",
                    "date": first["execution_date"],
                }
    return None


def _negative(provider_id: str, payload: Mapping[str, Any]) -> CorporateTerminal:
    data = payload.get("data")
    explicit = (
        provider_id == "eodhd"
        and payload.get("status_code") == 404
        and isinstance(data, str)
        and "not found" in data.lower()
    ) or (
        provider_id == "twelve-data"
        and payload.get("status_code") == 4042
        and isinstance(data, Mapping)
        and data.get("status") == "error"
        and isinstance(data.get("message"), str)
        and "invalid" in data["message"].lower()
    )
    if explicit:
        return CorporateTerminal(
            CellState.COMPLETED,
            FailureAttribution.PROVIDER_VALIDATION_ERROR,
            {"validation_error": "provider_validation_error"},
        )
    if provider_id in {"alpha-vantage", "massive-stocks"}:
        return CorporateTerminal(
            CellState.PROVIDER_NEGATIVE, FailureAttribution.EMPTY_OR_PARTIAL_DATA, {}
        )
    return _blocked(_transport_attribution(payload))


def _blocked(attribution: FailureAttribution) -> CorporateTerminal:
    return CorporateTerminal(CellState.INFRA_BLOCKED, attribution, {})


def _transport_attribution(payload: Mapping[str, Any]) -> FailureAttribution:
    status_code = payload.get("status_code")
    if status_code == 401:
        return FailureAttribution.AUTH_OR_ENTITLEMENT
    if status_code == 429:
        return FailureAttribution.RATE_LIMITED
    if isinstance(status_code, int) and status_code >= 500:
        return FailureAttribution.PROVIDER_RUNTIME_ERROR
    return FailureAttribution.EMPTY_OR_PARTIAL_DATA
