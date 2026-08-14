from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from qveris_bench.cap_packs.govt_bond_yield.models import (
    GovernmentBondRequestIdentity,
)
from qveris_bench.execution.direct_binding import DirectBinding
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.suite import BenchmarkCase
from qveris_bench.releases.public_terminal import ValidatedTerminalOutcome


@dataclass(frozen=True)
class GovernmentBondDirectResult:
    state: CellState
    facts: dict[str, object]
    unmet_conditions: tuple[str, ...]
    failure_attribution: FailureAttribution | None


def evaluate_government_bond_document(
    provider_id: str,
    payload: Mapping[str, Any],
    case: BenchmarkCase,
    *,
    request_identity: GovernmentBondRequestIdentity | None,
) -> GovernmentBondDirectResult:
    status_code = payload.get("status_code")
    if status_code in {401, 402, 403, 429} or (
        isinstance(status_code, int) and status_code >= 500
    ):
        return _infra_result(case, _transport_attribution(status_code))
    if case.negative_control:
        if _explicit_rejection(payload.get("data"), status_code):
            return GovernmentBondDirectResult(
                CellState.COMPLETED,
                {"validation_error": "provider_validation_error"},
                (),
                FailureAttribution.PROVIDER_VALIDATION_ERROR,
            )
        return GovernmentBondDirectResult(
            CellState.PROVIDER_NEGATIVE,
            {},
            ("validation_error",),
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    if status_code != 200 or request_identity is None:
        return _infra_result(case, FailureAttribution.EMPTY_OR_PARTIAL_DATA)

    extracted = _extract_latest(provider_id, payload.get("data"), case)
    if extracted is None:
        return GovernmentBondDirectResult(
            CellState.PROVIDER_NEGATIVE,
            {},
            tuple(case.completion_conditions),
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    row, observed_date, observed_value, metadata = extracted
    returned_identifier = _first_string(
        row, ("symbol", "series_id", "benchmark", "benchmark_id", "name")
    )
    identity_verified, identity_basis = _identity_evaluation(
        returned_identifier, request_identity
    )
    facts: dict[str, object] = {
        "symbol": returned_identifier or request_identity.vendor_identifier,
        "date": observed_date,
        "close": observed_value,
        "identity_verified": identity_verified,
        "identity_basis": identity_basis,
    }
    for key, aliases in {
        "unit": ("unit", "units"),
        "currency": ("currency",),
        "source": ("source", "provider"),
    }.items():
        value = _first_string(row, aliases) or _first_string(metadata, aliases)
        if value is not None:
            facts[key] = value
    if provider_id == "stlouisfed-fred" and "source" not in facts:
        facts["source"] = "FRED"
    unmet = () if identity_verified else ("identity_verified",)
    return GovernmentBondDirectResult(
        CellState.COMPLETED if not unmet else CellState.PROVIDER_NEGATIVE,
        facts,
        unmet,
        None if not unmet else FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )


def validate_public_outcome(
    case: BenchmarkCase, binding: DirectBinding, facts: dict[str, Any]
) -> ValidatedTerminalOutcome:
    failure = facts.get("execution_failure")
    if isinstance(failure, str) and facts == {"execution_failure": failure}:
        try:
            attribution = FailureAttribution(failure)
        except ValueError:
            attribution = None
        if attribution in {
            FailureAttribution.AUTH_OR_ENTITLEMENT,
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
            FailureAttribution.PROVIDER_RUNTIME_ERROR,
            FailureAttribution.RATE_LIMITED,
        }:
            return ValidatedTerminalOutcome(
                CellState.INFRA_BLOCKED,
                tuple(case.completion_conditions),
                attribution,
            )
    if case.negative_control:
        if facts == {"validation_error": "provider_validation_error"}:
            return ValidatedTerminalOutcome(
                CellState.COMPLETED,
                (),
                FailureAttribution.PROVIDER_VALIDATION_ERROR,
            )
        return ValidatedTerminalOutcome(
            CellState.PROVIDER_NEGATIVE,
            ("validation_error",),
            FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        )
    identity = GovernmentBondRequestIdentity.model_validate(binding.request_identity)
    value = _finite_number(facts.get("close"))
    observed_date = facts.get("date")
    symbol = facts.get("symbol")
    basis = facts.get("identity_basis")
    if basis == "request_bound":
        expected_identity = symbol == identity.vendor_identifier
        expected_basis = "request_bound"
    else:
        expected_identity, expected_basis = _identity_evaluation(
            symbol if isinstance(symbol, str) else None,
            identity,
        )
    identity_valid = (
        facts.get("identity_verified") is True
        and expected_identity
        and basis == expected_basis
    )
    if (
        value is not None
        and isinstance(observed_date, str)
        and _within_case_window(observed_date, case)
        and identity_valid
    ):
        return ValidatedTerminalOutcome(CellState.COMPLETED, (), None)
    return ValidatedTerminalOutcome(
        CellState.PROVIDER_NEGATIVE,
        tuple(case.completion_conditions),
        FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    )


def _extract_latest(
    provider_id: str, data: object, case: BenchmarkCase
) -> tuple[Mapping[str, Any], str, float, Mapping[str, Any]] | None:
    if not isinstance(data, Mapping):
        return None
    metadata: Mapping[str, Any] = data
    value_fields: tuple[str, ...]
    if provider_id == "stlouisfed-fred":
        candidate_rows = data.get("observations")
        value_fields = ("value", "close", "yield")
        series = data.get("seriess") or data.get("series")
        if isinstance(series, list) and series and isinstance(series[0], Mapping):
            metadata = series[0]
    elif provider_id == "qveris-finance":
        candidate_rows = data.get("data") or data.get("results") or data.get("rows")
        if isinstance(candidate_rows, Mapping):
            metadata = candidate_rows
            candidate_rows = (
                candidate_rows.get("data")
                or candidate_rows.get("results")
                or candidate_rows.get("rows")
            )
        value_fields = ("close", "yield", "value", "rate")
    else:
        return None
    if not isinstance(candidate_rows, list):
        return None
    valid: list[tuple[date, Mapping[str, Any], float]] = []
    for item in candidate_rows:
        if not isinstance(item, Mapping):
            continue
        observed_date = _first_string(item, ("date", "observation_date", "time"))
        value = _first_number(item, value_fields)
        parsed_date = _case_date(observed_date, case)
        if parsed_date is not None and value is not None:
            valid.append((parsed_date, item, value))
    if not valid:
        return None
    parsed_date, row, value = max(valid, key=lambda item: item[0])
    return row, parsed_date.isoformat(), value, metadata


def _identity_evaluation(
    returned_identifier: str | None, identity: GovernmentBondRequestIdentity
) -> tuple[bool, str]:
    if returned_identifier is None:
        return True, "request_bound"
    expected = {
        identity.vendor_identifier.strip().upper(),
        *(alias.strip().upper() for alias in identity.response_aliases),
    }
    return returned_identifier.strip().upper() in expected, "response_field"


def _first_string(row: Mapping[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_number(row: Mapping[str, Any], fields: tuple[str, ...]) -> float | None:
    for field in fields:
        value = _finite_number(row.get(field))
        if value is not None:
            return value
    return None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _case_date(value: str | None, case: BenchmarkCase) -> date | None:
    if value is None:
        return None
    try:
        observed = date.fromisoformat(value)
        start = date.fromisoformat(str(case.input["start_date"]))
        end = date.fromisoformat(str(case.input["end_date"]))
    except (KeyError, TypeError, ValueError):
        return None
    return observed if start <= observed <= end else None


def _within_case_window(value: str, case: BenchmarkCase) -> bool:
    return _case_date(value, case) is not None


def _explicit_rejection(data: object, status_code: object) -> bool:
    if status_code not in {200, 204, 400, 404, 422, 4042}:
        return False
    if isinstance(data, str):
        return any(
            term in data.lower()
            for term in ("invalid", "not found", "does not exist", "unsupported")
        )
    if isinstance(data, Mapping):
        return any(
            _explicit_rejection(value, status_code)
            for key, value in data.items()
            if str(key).lower().replace("_", "")
            in {"error", "errors", "errormessage", "validationerror", "message", "msg"}
        )
    if isinstance(data, list):
        return any(_explicit_rejection(item, status_code) for item in data)
    return False


def _infra_result(
    case: BenchmarkCase, attribution: FailureAttribution
) -> GovernmentBondDirectResult:
    return GovernmentBondDirectResult(
        CellState.INFRA_BLOCKED,
        {"execution_failure": attribution.value},
        tuple(case.completion_conditions),
        attribution,
    )


def _transport_attribution(status_code: object) -> FailureAttribution:
    if status_code in {401, 402, 403}:
        return FailureAttribution.AUTH_OR_ENTITLEMENT
    if status_code == 429:
        return FailureAttribution.RATE_LIMITED
    if isinstance(status_code, int) and status_code >= 500:
        return FailureAttribution.PROVIDER_RUNTIME_ERROR
    return FailureAttribution.EMPTY_OR_PARTIAL_DATA
