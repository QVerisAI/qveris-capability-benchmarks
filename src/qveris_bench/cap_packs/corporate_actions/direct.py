from __future__ import annotations

import csv
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Any

from qveris_bench.cap_packs.corporate_actions.models import (
    CorporateActionRequestIdentity,
)
from qveris_bench.execution.direct_binding import DirectBinding
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.releases.public_terminal import ValidatedTerminalOutcome


@dataclass(frozen=True)
class CorporateTerminal:
    state: CellState
    attribution: FailureAttribution | None
    facts: dict[str, object]


@dataclass(frozen=True)
class CorporateDirectResult:
    state: CellState
    facts: dict[str, object]
    unmet_conditions: tuple[str, ...]
    failure_attribution: FailureAttribution | None


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


def evaluate_corporate_action_document(
    provider_id: str,
    payload: Mapping[str, Any],
    case: BenchmarkCase,
    *,
    request_identity: CorporateActionRequestIdentity | None = None,
) -> CorporateDirectResult:
    status_code = payload.get("status_code")
    if status_code in {401, 429} or (
        isinstance(status_code, int) and status_code >= 500
    ):
        return _infra_result(case, _transport_attribution(payload))
    if case.negative_control:
        if _explicit_rejection(payload.get("data"), status_code):
            return CorporateDirectResult(
                CellState.COMPLETED,
                {"validation_error": "provider_validation_error"},
                (),
                FailureAttribution.PROVIDER_VALIDATION_ERROR,
            )
        return CorporateDirectResult(
            CellState.PROVIDER_NEGATIVE,
            {},
            ("validation_error",),
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    if status_code != 200 or request_identity is None:
        return _infra_result(case, FailureAttribution.EMPTY_OR_PARTIAL_DATA)

    event = _extract_event(provider_id, payload.get("data"), case)
    if event is None:
        return CorporateDirectResult(
            CellState.PROVIDER_NEGATIVE,
            {},
            tuple(case.completion_conditions),
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    event_date, ratio, returned_symbol = event
    identity_verified, identity_basis = _identity_evaluation(
        returned_symbol, request_identity
    )
    facts: dict[str, object] = {
        "symbol": request_identity.canonical_symbol,
        "identity_verified": identity_verified,
        "identity_basis": identity_basis,
        "action_type": "split",
        "date": event_date,
    }
    if returned_symbol is not None:
        facts["returned_symbol"] = returned_symbol
    if ratio is not None:
        facts["ratio"] = ratio
    unmet = () if identity_verified else ("identity_verified",)
    return CorporateDirectResult(
        CellState.COMPLETED if not unmet else CellState.PROVIDER_NEGATIVE,
        facts,
        unmet,
        None if not unmet else FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )


def _extract_event(
    provider_id: str, data: object, case: BenchmarkCase
) -> tuple[str, float | None, str | None] | None:
    rows: list[Mapping[str, Any]] = []
    returned_symbol: str | None = None
    date_fields: tuple[str, ...]
    ratio_fields: tuple[str, ...]
    if provider_id == "eodhd" and isinstance(data, str):
        rows = list(csv.DictReader(StringIO(data)))
        date_fields = ("Date",)
        ratio_fields = ("Stock Splits",)
    elif provider_id == "twelve-data" and isinstance(data, Mapping):
        meta = data.get("meta")
        if isinstance(meta, Mapping) and isinstance(meta.get("symbol"), str):
            returned_symbol = meta["symbol"]
        split_rows = data.get("splits")
        rows = [item for item in split_rows or () if isinstance(item, Mapping)]
        date_fields = ("date", "execution_date")
        ratio_fields = ("ratio", "split_factor")
    elif provider_id == "alpha-vantage" and isinstance(data, Mapping):
        if isinstance(data.get("symbol"), str):
            returned_symbol = data["symbol"]
        split_rows = data.get("data")
        rows = [item for item in split_rows or () if isinstance(item, Mapping)]
        date_fields = ("effective_date", "date")
        ratio_fields = ("split_factor", "ratio")
    elif provider_id == "massive-stocks" and isinstance(data, Mapping):
        split_rows = data.get("results")
        rows = [item for item in split_rows or () if isinstance(item, Mapping)]
        date_fields = ("execution_date", "date")
        ratio_fields = ("split_to", "ratio", "split_from")
    elif provider_id == "rongjuhui" and isinstance(data, Mapping):
        split_rows = data.get("data")
        rows = [item for item in split_rows or () if isinstance(item, Mapping)]
        date_fields = ("exDate", "reportDate", "date")
        ratio_fields = ("splitRatio", "ratio")
    else:
        return None

    for row in rows:
        event_date = _first_string(row, date_fields)
        if event_date is None or not _within_case_window(event_date, case):
            continue
        row_symbol = _first_string(row, ("symbol", "ticker", "code"))
        return (
            event_date,
            _positive_ratio(row, ratio_fields),
            row_symbol or returned_symbol,
        )
    return None


def _first_string(row: Mapping[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def _positive_ratio(row: Mapping[str, Any], fields: tuple[str, ...]) -> float | None:
    for field in fields:
        value = row.get(field)
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            continue
        if isinstance(value, str) and "/" in value:
            value = value.split("/", 1)[0]
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(ratio) and ratio > 0:
            return ratio
    return None


def _explicit_rejection(data: object, status_code: object) -> bool:
    if status_code not in {200, 204, 400, 404, 422, 4042}:
        return False
    if isinstance(data, str):
        lowered = data.lower()
        return any(term in lowered for term in ("invalid", "not found", "unknown"))
    if isinstance(data, Mapping):
        return any(
            isinstance(value, str)
            and any(
                term in value.lower() for term in ("invalid", "not found", "unknown")
            )
            for key, value in data.items()
            if str(key).lower().replace("_", "")
            in {"error", "errors", "errormessage", "validationerror", "message", "msg"}
        ) or any(
            _explicit_rejection(value, status_code)
            for value in data.values()
            if isinstance(value, (Mapping, list))
        )
    if isinstance(data, list):
        return any(_explicit_rejection(item, status_code) for item in data)
    return False


def _identity_evaluation(
    returned_symbol: str | None, identity: CorporateActionRequestIdentity
) -> tuple[bool, str]:
    if returned_symbol is None:
        return True, "request_bound"
    returned = returned_symbol.strip().upper()
    expected = {
        identity.vendor_symbol.strip().upper(),
        identity.canonical_symbol.strip().upper(),
    }
    if returned in expected:
        return True, "response_field"
    if (
        ":" not in returned
        and "." not in returned
        and _symbol_code(returned) in {_symbol_code(item) for item in expected}
    ):
        return True, "request_bound"
    return False, "response_field"


def _symbol_code(value: str) -> str:
    code = value.split(":", 1)[0].split(".", 1)[0].lstrip("0")
    return code or "0"


def validate_public_outcome(
    case: BenchmarkCase, binding: DirectBinding, facts: dict[str, Any]
) -> ValidatedTerminalOutcome:
    execution_failure = facts.get("execution_failure")
    if isinstance(execution_failure, str):
        allowed = {
            FailureAttribution.AUTH_OR_ENTITLEMENT,
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
            FailureAttribution.PROVIDER_RUNTIME_ERROR,
            FailureAttribution.RATE_LIMITED,
        }
        try:
            attribution = FailureAttribution(execution_failure)
        except ValueError:
            attribution = None
        if attribution in allowed and facts == {"execution_failure": execution_failure}:
            return ValidatedTerminalOutcome(
                CellState.INFRA_BLOCKED,
                tuple(case.completion_conditions),
                attribution,
            )
    if case.negative_control:
        if facts == {"validation_error": "provider_validation_error"}:
            return ValidatedTerminalOutcome(
                CellState.COMPLETED, (), FailureAttribution.PROVIDER_VALIDATION_ERROR
            )
        unmet = (
            ("validation_error",)
            if str(case.case_id).endswith("-v2")
            else ("provider_validation_error",)
        )
        return ValidatedTerminalOutcome(
            CellState.PROVIDER_NEGATIVE,
            unmet,
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    symbol = case.input.get("symbol")
    event_date = facts.get("date")
    identity_valid = True
    if binding.request_identity is not None:
        identity = CorporateActionRequestIdentity.model_validate(
            binding.request_identity
        )
        basis = facts.get("identity_basis")
        returned = facts.get("returned_symbol")
        expected_verified, expected_basis = _identity_evaluation(
            returned if isinstance(returned, str) else None, identity
        )
        identity_valid = (
            facts.get("identity_verified") is True
            and identity.canonical_symbol == symbol
            and expected_verified
            and basis == expected_basis
        )
    if (
        facts.get("symbol") == symbol
        and facts.get("action_type") == "split"
        and isinstance(event_date, str)
        and _within_case_window(event_date, case)
        and identity_valid
    ):
        return ValidatedTerminalOutcome(CellState.COMPLETED, (), None)
    return ValidatedTerminalOutcome(
        (
            CellState.PROVIDER_NEGATIVE
            if binding.request_identity is not None
            else CellState.INFRA_BLOCKED
        ),
        (
            ("symbol", "identity_verified", "action_type", "date")
            if binding.request_identity is not None
            else ("symbol", "action_type", "date")
        ),
        FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )


def _infra_result(
    case: BenchmarkCase, attribution: FailureAttribution
) -> CorporateDirectResult:
    return CorporateDirectResult(
        CellState.INFRA_BLOCKED,
        {"execution_failure": attribution.value},
        tuple(case.completion_conditions),
        attribution,
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
