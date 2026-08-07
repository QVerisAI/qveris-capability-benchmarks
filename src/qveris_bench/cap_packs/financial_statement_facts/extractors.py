from __future__ import annotations

from typing import Any


class FinancialStatementExtractionError(ValueError):
    pass


def extract_fmp_income_statement(
    document: object, symbol: str, fiscal_year: int, *, negative_control: bool = False
) -> dict[str, Any]:
    data = _unwrap(document)
    if not isinstance(data, dict):
        raise FinancialStatementExtractionError("response must be an object")
    reports = _reports(data, ("annualReports", "reports"))
    if negative_control:
        if _report_for_year(reports, fiscal_year) is not None:
            raise FinancialStatementExtractionError(
                "negative control returned a fiscal year fact"
            )
        return {"validation_error": "fiscal year unavailable"}
    report = _required_report_for_year(reports, fiscal_year)
    revenue = _number(report.get("revenue"), "revenue")
    return _facts(symbol, fiscal_year, revenue, report)


def extract_alpha_vantage_income_statement(
    document: object, symbol: str, fiscal_year: int, *, negative_control: bool = False
) -> dict[str, Any]:
    data = _unwrap(document)
    if not isinstance(data, dict):
        raise FinancialStatementExtractionError("response must be an object")
    reports = _reports(data, ("annualReports",))
    if negative_control:
        if _report_for_year(reports, fiscal_year) is not None:
            raise FinancialStatementExtractionError(
                "negative control returned a fiscal year fact"
            )
        return {"validation_error": "fiscal year unavailable"}
    report = _required_report_for_year(reports, fiscal_year)
    revenue = _number(report.get("totalRevenue"), "revenue")
    return _facts(symbol, fiscal_year, revenue, report)


def extract_sec_company_facts(
    document: object, symbol: str, fiscal_year: int, *, negative_control: bool = False
) -> dict[str, Any]:
    data = _unwrap(document)
    if not isinstance(data, dict):
        raise FinancialStatementExtractionError("response must be an object")
    facts = data.get("facts")
    if not isinstance(facts, dict):
        raise FinancialStatementExtractionError("facts are missing")
    gaap = facts.get("us-gaap")
    if not isinstance(gaap, dict):
        raise FinancialStatementExtractionError("us-gaap facts are missing")
    revenue_facts = gaap.get("Revenue")
    if not isinstance(revenue_facts, dict):
        raise FinancialStatementExtractionError("Revenue facts are missing")
    units = revenue_facts.get("units")
    if not isinstance(units, dict):
        raise FinancialStatementExtractionError("Revenue units are missing")
    rows = units.get("USD", [])
    if not isinstance(rows, list):
        raise FinancialStatementExtractionError("Revenue rows must be an array")
    if negative_control:
        if _sec_row_for_year(rows, fiscal_year) is not None:
            raise FinancialStatementExtractionError(
                "negative control returned a fiscal year fact"
            )
        return {"validation_error": "fiscal year unavailable"}
    row = _required_sec_row_for_year(rows, fiscal_year)
    revenue = _number(row.get("val"), "revenue")
    return _facts(symbol, fiscal_year, revenue, row)


def _unwrap(document: object) -> object:
    if not isinstance(document, dict):
        return document
    result = document.get("result")
    if isinstance(result, dict) and "data" in result:
        return result.get("data")
    return document


def _reports(data: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            reports: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, dict):
                    raise FinancialStatementExtractionError(f"{key} must hold objects")
                reports.append(item)
            return reports
    raise FinancialStatementExtractionError("reported statements are missing")


def _report_year(report: dict[str, Any]) -> int | None:
    date = report.get("date") or report.get("fiscalDateEnding")
    if not isinstance(date, str) or len(date) < 4:
        return None
    try:
        return int(date[:4])
    except ValueError:
        return None


def _report_for_year(
    reports: list[dict[str, Any]], fiscal_year: int
) -> dict[str, Any] | None:
    matches = [report for report in reports if _report_year(report) == fiscal_year]
    return matches[0] if matches else None


def _required_report_for_year(
    reports: list[dict[str, Any]], fiscal_year: int
) -> dict[str, Any]:
    report = _report_for_year(reports, fiscal_year)
    if report is None:
        raise FinancialStatementExtractionError("fiscal year unavailable")
    return report


def _sec_row_year(row: dict[str, Any]) -> int | None:
    fy = row.get("fy")
    if isinstance(fy, int):
        return fy
    end = row.get("end")
    if isinstance(end, str) and len(end) >= 4:
        try:
            return int(end[:4])
        except ValueError:
            return None
    return None


def _sec_row_for_year(
    rows: list[dict[str, Any]], fiscal_year: int
) -> dict[str, Any] | None:
    matches = [row for row in rows if _sec_row_year(row) == fiscal_year]
    return matches[0] if matches else None


def _required_sec_row_for_year(
    rows: list[dict[str, Any]], fiscal_year: int
) -> dict[str, Any]:
    row = _sec_row_for_year(rows, fiscal_year)
    if row is None:
        raise FinancialStatementExtractionError("fiscal year unavailable")
    return row


def _number(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise FinancialStatementExtractionError(f"{field} is invalid")
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as exc:
            raise FinancialStatementExtractionError(f"{field} is invalid") from exc
    if not isinstance(value, (int, float)):
        raise FinancialStatementExtractionError(f"{field} is invalid")
    numeric = float(value)
    if numeric <= 0:
        raise FinancialStatementExtractionError(f"{field} is invalid")
    return numeric


def _facts(
    symbol: str, fiscal_year: int, revenue: float, source: dict[str, Any]
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "symbol": symbol,
        "fiscal_year": str(fiscal_year),
        "revenue": revenue,
        "currency": "USD",
    }
    filing_date = source.get("date") or source.get("end")
    if isinstance(filing_date, str) and filing_date:
        facts["filing_date"] = filing_date
    return facts
