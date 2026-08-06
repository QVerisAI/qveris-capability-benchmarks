from __future__ import annotations

from typing import Any


class EtfHoldingsExtractionError(ValueError):
    pass


def extract_alpha_vantage_etf_holdings(
    document: object, symbol: str, *, negative_control: bool = False
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise EtfHoldingsExtractionError("response must be an object")
    holdings = _holdings(document)
    if negative_control:
        if holdings:
            raise EtfHoldingsExtractionError("negative control returned holdings")
        if not _has_invalid_symbol_error(document, symbol):
            raise EtfHoldingsExtractionError(
                "negative control lacks a validation error"
            )
        return {"validation_error": "provider returned explicit validation response"}
    if not holdings:
        raise EtfHoldingsExtractionError("positive control returned no holdings")

    identifiers: list[str] = []
    weights: list[float] = []
    for holding in holdings:
        if not isinstance(holding, dict):
            raise EtfHoldingsExtractionError("holding must be an object")
        identifier = holding.get("symbol")
        if not isinstance(identifier, str) or not identifier:
            raise EtfHoldingsExtractionError("holding symbol is missing")
        identifiers.append(identifier)
        weights.append(_weight(holding.get("weight")))
    return {"symbol": symbol, "holdings": identifiers, "weights": weights}


def _holdings(document: dict[str, Any]) -> list[Any]:
    result = document.get("result")
    if not isinstance(result, dict):
        raise EtfHoldingsExtractionError("result is missing")
    data = result.get("data")
    if not isinstance(data, dict):
        raise EtfHoldingsExtractionError("result data is missing")
    holdings = data.get("holdings", [])
    if not isinstance(holdings, list):
        raise EtfHoldingsExtractionError("holdings must be an array")
    return holdings


def _weight(value: object) -> float:
    if isinstance(value, bool):
        raise EtfHoldingsExtractionError("weight is invalid")
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str) and value.endswith("%"):
        try:
            numeric = float(value[:-1]) / 100
        except ValueError as exc:
            raise EtfHoldingsExtractionError("weight is invalid") from exc
    elif isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError as exc:
            raise EtfHoldingsExtractionError("weight is invalid") from exc
    else:
        raise EtfHoldingsExtractionError("weight is invalid")
    if not 0 <= numeric <= 1:
        raise EtfHoldingsExtractionError("weight is outside [0, 1]")
    return numeric


def _has_invalid_symbol_error(document: dict[str, Any], symbol: str) -> bool:
    result = document.get("result")
    if not isinstance(result, dict):
        return False
    candidates = [result.get("error_code"), result.get("code")]
    error = result.get("error")
    if isinstance(error, dict):
        candidates.append(error.get("code"))
    if any(
        isinstance(candidate, str)
        and candidate.casefold().replace("-", "_")
        in {"invalid_symbol", "invalid_etf", "unknown_symbol"}
        for candidate in candidates
    ):
        return True
    message = document.get("error_message")
    if not isinstance(message, str):
        return False
    normalized = message.casefold()
    blocked_terms = (
        "api key",
        "auth",
        "rate",
        "limit",
        "internal",
        "server",
        "request",
    )
    return (
        symbol.casefold() in normalized
        and "invalid" in normalized
        and ("symbol" in normalized or "etf" in normalized)
        and not any(term in normalized for term in blocked_terms)
    )
