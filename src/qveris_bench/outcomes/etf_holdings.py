from __future__ import annotations

from typing import Any


class EtfHoldingsExtractionError(ValueError):
    pass


def extract_alpha_vantage_etf_holdings(
    document: dict[str, Any], symbol: str, *, negative_control: bool = False
) -> dict[str, Any]:
    holdings = _holdings(document)
    if negative_control:
        if holdings:
            raise EtfHoldingsExtractionError("negative control returned holdings")
        return {"validation_error": "provider returned no holdings"}
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
    else:
        raise EtfHoldingsExtractionError("weight is invalid")
    if not 0 <= numeric <= 1:
        raise EtfHoldingsExtractionError("weight is outside [0, 1]")
    return numeric
