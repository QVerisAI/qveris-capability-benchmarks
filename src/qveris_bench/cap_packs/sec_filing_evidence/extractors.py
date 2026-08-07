from __future__ import annotations

from typing import Any


class SecFilingExtractionError(ValueError):
    pass


def extract_massive_stocks_risk_factors(
    document: object, symbol: str, *, negative_control: bool = False
) -> dict[str, Any]:
    rows = _massive_rows(document)
    if negative_control:
        if rows:
            raise SecFilingExtractionError("filing type not supported")
        return {"validation_error": "no risk factors returned"}
    if not rows:
        raise SecFilingExtractionError("filing unavailable")
    for row in rows:
        text = row.get("text")
        if isinstance(text, str) and _mentions_supply_chain(text):
            filing_id = _massive_filing_id(row)
            return {
                "symbol": symbol,
                "filing_id": filing_id,
                "evidence": text,
                "citation": _massive_citation(row),
            }
    raise SecFilingExtractionError("evidence passage missing")


def extract_fmp_10k(
    document: object, symbol: str, fiscal_year: int, *, negative_control: bool = False
) -> dict[str, Any]:
    data = _unwrap(document)
    if not isinstance(data, dict):
        raise SecFilingExtractionError("response must be an object")
    if negative_control:
        raise SecFilingExtractionError("filing type not supported")
    passage = _find_supply_chain_text(data)
    if passage is None:
        raise SecFilingExtractionError("evidence passage missing")
    return {
        "symbol": symbol,
        "filing_id": f"{symbol}-10-K-{fiscal_year}",
        "evidence": passage,
        "citation": f"10-K fiscal year {fiscal_year}",
    }


def extract_fmp_sec_filings(
    document: object, symbol: str, *, negative_control: bool = False
) -> dict[str, Any]:
    data = _unwrap(document)
    if not isinstance(data, dict):
        raise SecFilingExtractionError("response must be an object")
    if negative_control:
        if _fmp_explicit_error(data) or _fmp_filings(data) == []:
            return {"validation_error": "unsupported filing type"}
        raise SecFilingExtractionError("filing type not supported")
    filing = _fmp_filing_for_10k(data, symbol)
    if filing is None:
        raise SecFilingExtractionError("filing unavailable")
    raise SecFilingExtractionError("evidence passage missing")


def _unwrap(document: object) -> object:
    if not isinstance(document, dict):
        return document
    result = document.get("result")
    if isinstance(result, dict) and "data" in result:
        return result.get("data")
    return document


def _massive_rows(document: object) -> list[dict[str, Any]]:
    data = _unwrap(document)
    if not isinstance(data, dict):
        raise SecFilingExtractionError("response must be an object")
    envelope = data.get("data")
    if isinstance(envelope, dict):
        rows = envelope.get("results", [])
    else:
        rows = envelope if envelope is not None else []
    if not isinstance(rows, list):
        raise SecFilingExtractionError("risk factors must be an array")
    if "data" not in data and "error_message" not in data:
        raise SecFilingExtractionError("risk factors are missing")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise SecFilingExtractionError("risk factor must be an object")
        normalized.append(row)
    return normalized


def _massive_filing_id(row: dict[str, Any]) -> str:
    cik = row.get("cik")
    filing_date = row.get("filing_date")
    if isinstance(cik, str) and isinstance(filing_date, str) and filing_date:
        return f"{cik}-{filing_date}"
    ticker = row.get("ticker")
    if isinstance(ticker, str) and isinstance(filing_date, str) and filing_date:
        return f"{ticker}-{filing_date}"
    raise SecFilingExtractionError("filing identity missing")


def _massive_citation(row: dict[str, Any]) -> str:
    filing_date = row.get("filing_date")
    cik = row.get("cik")
    if isinstance(filing_date, str) and isinstance(cik, str):
        return f"10-K filed {filing_date} (CIK {cik})"
    raise SecFilingExtractionError("citation missing")


def _mentions_supply_chain(text: str) -> bool:
    normalized = text.casefold()
    return "supply chain" in normalized or "supply-chain" in normalized


def _find_supply_chain_text(value: object) -> str | None:
    if isinstance(value, str):
        return value if _mentions_supply_chain(value) else None
    if isinstance(value, dict):
        for nested in value.values():
            match = _find_supply_chain_text(nested)
            if match is not None:
                return match
    elif isinstance(value, list):
        for nested in value:
            match = _find_supply_chain_text(nested)
            if match is not None:
                return match
    return None


def _fmp_filings(data: dict[str, Any]) -> list[dict[str, Any]]:
    filings = data.get("filings", data.get("data"))
    if not isinstance(filings, list):
        return []
    return [item for item in filings if isinstance(item, dict)]


def _fmp_explicit_error(data: dict[str, Any]) -> bool:
    message = data.get("error_message")
    return isinstance(message, str) and bool(message)


def _fmp_filing_for_10k(data: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    for filing in _fmp_filings(data):
        if filing.get("form") != "10-K":
            continue
        cik = filing.get("cik")
        if isinstance(cik, str) and cik not in {symbol, "0000320193"}:
            continue
        return filing
    return None
