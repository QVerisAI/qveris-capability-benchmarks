from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from qveris_bench.cap_packs.crypto_spot_quote.extractors import (
    CryptoSpotQuoteExtractionError,
    extract_binance_quote,
    extract_okx_quote,
)
from qveris_bench.models.enums import CellState, FailureAttribution


@dataclass(frozen=True)
class Terminal:
    state: CellState
    attribution: FailureAttribution | None
    facts: dict[str, object]


def evaluate(provider_id: str, case_id: str, payload: Mapping[str, Any]) -> Terminal:
    if case_id == "crypto-invalid-spot-symbol":
        return _negative(provider_id, payload)
    if case_id != "crypto-btcusdt-spot-quote":
        return _blocked(FailureAttribution.BENCHMARK_SYSTEM_ERROR)
    data = payload.get("data")
    if not isinstance(data, Mapping) or payload.get("status_code") != 200:
        return _blocked(_transport_attribution(payload))
    try:
        if provider_id == "binance":
            facts = extract_binance_quote(data, expected_symbol="BTCUSDT")
        elif provider_id == "okx":
            facts = extract_okx_quote(data, expected_symbol="BTCUSDT")
        else:
            return _blocked(FailureAttribution.BENCHMARK_SYSTEM_ERROR)
    except CryptoSpotQuoteExtractionError:
        return _blocked(FailureAttribution.EMPTY_OR_PARTIAL_DATA)
    return Terminal(CellState.COMPLETED, None, facts)


def _negative(provider_id: str, payload: Mapping[str, Any]) -> Terminal:
    data = payload.get("data")
    if provider_id == "binance" and _binance_rejected(payload, data):
        return _rejected()
    if provider_id == "okx" and _okx_rejected(payload, data):
        return _rejected()
    return _blocked(_transport_attribution(payload))


def _binance_rejected(payload: Mapping[str, Any], data: object) -> bool:
    return (
        payload.get("status_code") == 400
        and isinstance(data, Mapping)
        and data.get("code") == -1121
        and isinstance(data.get("msg"), str)
        and "invalid symbol" in data["msg"].lower()
    )


def _okx_rejected(payload: Mapping[str, Any], data: object) -> bool:
    return (
        payload.get("status_code") == 200
        and isinstance(data, Mapping)
        and data.get("code") == "51001"
        and data.get("data") == []
    )


def _rejected() -> Terminal:
    return Terminal(
        CellState.PROVIDER_NEGATIVE, FailureAttribution.PROVIDER_VALIDATION_ERROR, {}
    )


def _blocked(attribution: FailureAttribution) -> Terminal:
    return Terminal(CellState.INFRA_BLOCKED, attribution, {})


def _transport_attribution(payload: Mapping[str, Any]) -> FailureAttribution:
    status_code = payload.get("status_code")
    if status_code == 401:
        return FailureAttribution.AUTH_OR_ENTITLEMENT
    if status_code == 429:
        return FailureAttribution.RATE_LIMITED
    if isinstance(status_code, int) and status_code >= 500:
        return FailureAttribution.PROVIDER_RUNTIME_ERROR
    return FailureAttribution.EMPTY_OR_PARTIAL_DATA
