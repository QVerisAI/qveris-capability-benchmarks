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


def extract_eodhd_stock_quote(
    document: object, symbol: str, *, negative_control: bool = False
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise StockQuoteExtractionError("response must be an object")
    if negative_control:
        if not _eodhd_negative_response(document):
            raise StockQuoteExtractionError(
                "negative control lacks an explicit validation response"
            )
        return {"validation_error": "provider returned explicit validation response"}

    quote = _eodhd_quote(document, symbol)
    price = _positive_number(quote.get("lastTradePrice"), "price")
    timestamp = _timestamp_milliseconds(quote.get("lastTradeTime"))
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
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise StockQuoteExtractionError(f"{field} is invalid") from exc
    if not isfinite(numeric) or numeric <= 0:
        raise StockQuoteExtractionError(f"{field} is invalid")
    return numeric


def _timestamp(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StockQuoteExtractionError("timestamp is invalid")
    try:
        timestamp = float(value)
    except (OverflowError, ValueError) as exc:
        raise StockQuoteExtractionError("timestamp is invalid") from exc
    if not isfinite(timestamp) or timestamp <= 0 or not timestamp.is_integer():
        raise StockQuoteExtractionError("timestamp is invalid")
    try:
        return datetime.fromtimestamp(int(timestamp), UTC).isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise StockQuoteExtractionError("timestamp is invalid") from exc


def _timestamp_milliseconds(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StockQuoteExtractionError("timestamp is invalid")
    try:
        milliseconds = float(value)
    except (OverflowError, ValueError) as exc:
        raise StockQuoteExtractionError("timestamp is invalid") from exc
    if not isfinite(milliseconds) or milliseconds <= 0 or not milliseconds.is_integer():
        raise StockQuoteExtractionError("timestamp is invalid")
    return _timestamp(int(milliseconds) / 1000)


def _eodhd_quote(document: dict[str, Any], symbol: str) -> dict[str, Any]:
    result = document.get("result")
    if not isinstance(result, dict):
        raise StockQuoteExtractionError("result is missing")
    envelope = result.get("data")
    if not isinstance(envelope, dict):
        raise StockQuoteExtractionError("result data is missing")
    rows = envelope.get("data")
    if not isinstance(rows, dict):
        raise StockQuoteExtractionError("quote data is missing")
    expected_symbols = {symbol, f"{symbol}.US"}
    matches = [
        quote
        for key, quote in rows.items()
        if key in expected_symbols and isinstance(quote, dict)
    ]
    if len(matches) != 1:
        raise StockQuoteExtractionError("quote is missing")
    return matches[0]


def _eodhd_negative_response(document: dict[str, Any]) -> bool:
    error_message = document.get("error_message")
    if not isinstance(error_message, str) or not error_message:
        return False
    message = error_message.lower()
    if any(
        term in message
        for term in (
            "unauthorized",
            "forbidden",
            "authentication",
            "rate limit",
            "quota",
            "server error",
            "internal error",
            "timeout",
            "temporarily unavailable",
        )
    ):
        return False
    if not any(
        marker in message
        for marker in ("unknown symbol", "invalid symbol", "symbol not found")
    ):
        return False
    result = document.get("result")
    if not isinstance(result, dict):
        return False
    envelope = result.get("data")
    if not isinstance(envelope, dict):
        return False
    return envelope.get("data") == []


def _is_unavailable_quote(data: dict[str, Any]) -> bool:
    return (
        _is_numeric_zero(data.get("c"))
        and _is_numeric_zero(data.get("t"))
        and data.get("d") is None
        and data.get("dp") is None
        and all(_is_numeric_zero(data.get(field)) for field in ("h", "l", "o", "pc"))
    )


def _is_numeric_zero(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(value) and value == 0
    except OverflowError:
        return False
