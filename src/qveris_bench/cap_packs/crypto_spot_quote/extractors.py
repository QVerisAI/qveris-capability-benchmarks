from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CryptoSpotQuoteExtractionError(ValueError):
    pass


def extract_binance_quote(
    data: Mapping[str, Any], *, expected_symbol: str
) -> dict[str, object]:
    returned_symbol = _string(data, "symbol")
    if returned_symbol != expected_symbol:
        raise CryptoSpotQuoteExtractionError("Binance response symbol does not match")
    return _quote_facts(
        symbol=returned_symbol,
        price=_number(data, "lastPrice"),
        open_price=_number(data, "openPrice"),
        high=_number(data, "highPrice"),
        low=_number(data, "lowPrice"),
        timestamp=_timestamp(data, "closeTime"),
        exchange="BINANCE",
    )


def extract_okx_quote(
    data: Mapping[str, Any], *, expected_symbol: str
) -> dict[str, object]:
    if _string(data, "code") != "0":
        raise CryptoSpotQuoteExtractionError("OKX response is not successful")
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise CryptoSpotQuoteExtractionError("OKX response must contain one ticker")
    row = rows[0]
    if _string(row, "instType") != "SPOT":
        raise CryptoSpotQuoteExtractionError("OKX response is not a spot ticker")
    if _string(row, "instId") != "BTC-USDT" or expected_symbol != "BTCUSDT":
        raise CryptoSpotQuoteExtractionError("OKX response symbol does not match")
    return _quote_facts(
        symbol=expected_symbol,
        price=_number(row, "last"),
        open_price=_number(row, "open24h"),
        high=_number(row, "high24h"),
        low=_number(row, "low24h"),
        timestamp=_timestamp(row, "ts"),
        exchange="OKX",
    )


def _quote_facts(
    *,
    symbol: str,
    price: float,
    open_price: float,
    high: float,
    low: float,
    timestamp: int,
    exchange: str,
) -> dict[str, object]:
    if min(price, open_price, high, low) <= 0 or high < low:
        raise CryptoSpotQuoteExtractionError("quote values are invalid")
    return {
        "symbol": symbol,
        "price": price,
        "open": open_price,
        "high": high,
        "low": low,
        "timestamp": timestamp,
        "exchange": exchange,
        "currency": "USDT",
    }


def _string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise CryptoSpotQuoteExtractionError(f"missing {key}")
    return value


def _number(data: Mapping[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CryptoSpotQuoteExtractionError(f"invalid {key}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CryptoSpotQuoteExtractionError(f"invalid {key}") from exc
    return number


def _timestamp(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CryptoSpotQuoteExtractionError(f"invalid {key}")
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as exc:
        raise CryptoSpotQuoteExtractionError(f"invalid {key}") from exc
    if timestamp <= 0:
        raise CryptoSpotQuoteExtractionError(f"invalid {key}")
    return timestamp
