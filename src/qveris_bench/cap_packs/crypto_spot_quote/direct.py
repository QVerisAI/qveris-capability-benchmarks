from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from qveris_bench.models.enums import CellState, FailureAttribution


@dataclass(frozen=True)
class Terminal:
    state: CellState
    attribution: FailureAttribution | None
    facts: dict[str, object]


def evaluate(provider_id: str, case_id: str, payload: Mapping[str, Any]) -> Terminal:
    if case_id == "crypto-invalid-spot-symbol":
        return _negative(payload)
    data = payload.get("data")
    if not isinstance(data, Mapping) or payload.get("status_code") != 200:
        return _incomplete()
    try:
        if provider_id == "binance":
            facts = _binance(data)
        elif provider_id == "okx":
            facts = _okx(data)
        else:
            return _incomplete()
    except ValueError:
        return _incomplete()
    return Terminal(CellState.COMPLETED, None, facts)


def _negative(payload: Mapping[str, Any]) -> Terminal:
    data = payload.get("data")
    rejected = payload.get("status_code") != 200
    if isinstance(data, Mapping):
        rejected = rejected or (
            isinstance(data.get("code"), str) and data["code"] != "0"
        )
    return Terminal(
        CellState.PROVIDER_NEGATIVE,
        FailureAttribution.PROVIDER_VALIDATION_ERROR
        if rejected
        else FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        {},
    )


def _incomplete() -> Terminal:
    return Terminal(
        CellState.PROVIDER_NEGATIVE, FailureAttribution.EMPTY_OR_PARTIAL_DATA, {}
    )


def _binance(data: Mapping[str, Any]) -> dict[str, object]:
    if data.get("symbol") != "BTCUSDT":
        raise ValueError("wrong symbol")
    return _facts(
        data, "lastPrice", "openPrice", "highPrice", "lowPrice", "closeTime", "BINANCE"
    )


def _okx(data: Mapping[str, Any]) -> dict[str, object]:
    rows = data.get("data")
    if data.get("code") != "0" or not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("invalid response")
    row = rows[0]
    if (
        not isinstance(row, Mapping)
        or row.get("instType") != "SPOT"
        or row.get("instId") != "BTC-USDT"
    ):
        raise ValueError("wrong instrument")
    return _facts(row, "last", "open24h", "high24h", "low24h", "ts", "OKX")


def _facts(
    data: Mapping[str, Any],
    price_key: str,
    open_key: str,
    high_key: str,
    low_key: str,
    timestamp_key: str,
    exchange: str,
) -> dict[str, object]:
    values = {
        "price": data.get(price_key),
        "open": data.get(open_key),
        "high": data.get(high_key),
        "low": data.get(low_key),
    }
    try:
        facts = {
            name: float(value)
            for name, value in values.items()
            if isinstance(value, (int, float, str)) and not isinstance(value, bool)
        }
        timestamp = int(data[timestamp_key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("missing required quote field") from exc
    if len(facts) != len(values):
        raise ValueError("missing required quote field")
    if min(facts.values()) <= 0 or facts["high"] < facts["low"] or timestamp <= 0:
        raise ValueError("invalid quote field")
    return {
        "symbol": "BTCUSDT",
        **facts,
        "timestamp": timestamp,
        "exchange": exchange,
        "currency": "USDT",
    }
