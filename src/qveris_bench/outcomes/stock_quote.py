from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any


class StockQuoteExtractionError(ValueError):
    pass


def extract_finnhub_stock_quote(
    document: object, symbol: str, *, negative_control: bool = False
) -> dict[str, Any]:
    data = _quote_data(document)
    if negative_control:
        if not _is_unavailable_quote(data):
            raise StockQuoteExtractionError(
                "negative control lacks an unavailable quote"
            )
        return {"validation_error": "provider returned an unavailable quote"}
    price = _positive_number(data.get("c"), "price")
    timestamp = _timestamp(data.get("t"))
    return {"symbol": symbol, "price": price, "timestamp": timestamp}


def _quote_data(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise StockQuoteExtractionError("response must be an object")
    result = document.get("result")
    if not isinstance(result, dict):
        raise StockQuoteExtractionError("result is missing")
    data = result.get("data")
    if not isinstance(data, dict):
        raise StockQuoteExtractionError("result data is missing")
    return data


def _positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StockQuoteExtractionError(f"{field} is invalid")
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0:
        raise StockQuoteExtractionError(f"{field} is invalid")
    return numeric


def _timestamp(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StockQuoteExtractionError("timestamp is invalid")
    timestamp = float(value)
    if not isfinite(timestamp) or timestamp <= 0 or not timestamp.is_integer():
        raise StockQuoteExtractionError("timestamp is invalid")
    try:
        return datetime.fromtimestamp(int(timestamp), UTC).isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise StockQuoteExtractionError("timestamp is invalid") from exc


def _is_unavailable_quote(data: dict[str, Any]) -> bool:
    return (
        _is_numeric_zero(data.get("c"))
        and _is_numeric_zero(data.get("t"))
        and data.get("d") is None
        and data.get("dp") is None
        and all(_is_numeric_zero(data.get(field)) for field in ("h", "l", "o", "pc"))
    )


def _is_numeric_zero(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
        and value == 0
    )
