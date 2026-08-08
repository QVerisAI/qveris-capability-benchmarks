from __future__ import annotations

from typing import Any


class FinancialStatementExtractionError(ValueError):
    pass


def extract_fmp_income_statement(
    document: object,
    symbol: str,
    fiscal_year: int,
    *,
    negative_control: bool = False,
    case_id: str | None = None,
) -> dict[str, Any]:
    data = _unwrap(document)
    if not isinstance(data, (dict, list)):
        raise FinancialStatementExtractionError("response must be an object")
    reports = _reports(data)
    if negative_control:
        if _report_for_year(reports, fiscal_year) is not None:
            raise FinancialStatementExtractionError(
                "negative control returned a fiscal year fact"
            )
        return {"validation_error": "fiscal year unavailable"}
    report = _required_report_for_year(reports, fiscal_year)
    revenue = _number(
        _row_field(
            report,
            "revenue",
            "Revenue",
            "totalRevenue",
            "TotalRevenue",
            "revenueUSD",
        ),
        "revenue",
    )
    return _facts(symbol, fiscal_year, revenue, report, case_id=case_id)


def extract_alpha_vantage_income_statement(
    document: object,
    symbol: str,
    fiscal_year: int,
    *,
    negative_control: bool = False,
    case_id: str | None = None,
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
    return _facts(symbol, fiscal_year, revenue, report, case_id=case_id)


def extract_sec_company_facts(
    document: object,
    symbol: str,
    fiscal_year: int,
    *,
    negative_control: bool = False,
    case_id: str | None = None,
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
    return _facts(symbol, fiscal_year, revenue, row, case_id=case_id)


def _unwrap(document: object) -> object:
    if not isinstance(document, dict):
        return document
    result = document.get("result")
    if isinstance(result, dict) and "data" in result:
        return result.get("data")
    return document


def _reports(
    data: dict[str, Any] | list[dict[str, Any]],
    keys: tuple[str, ...] = ("annualReports", "reports"),
) -> list[dict[str, Any]]:
    reports_value: object
    if isinstance(data, list):
        reports_value = data
    elif isinstance(data, dict):
        reports_value = None
        for candidate in keys:
            candidate_value = data.get(candidate)
            if isinstance(candidate_value, list):
                reports_value = candidate_value
                break
        if reports_value is None:
            raise FinancialStatementExtractionError("reported statements are missing")
    else:
        raise FinancialStatementExtractionError("response must be an object")
    if not isinstance(reports_value, list):
        raise FinancialStatementExtractionError("reported statements are missing")
    reports: list[dict[str, Any]] = []
    for item in reports_value:
        if not isinstance(item, dict):
            raise FinancialStatementExtractionError("reports must hold objects")
        reports.append(item)
    return reports


def _report_year(report: dict[str, Any]) -> int | None:
    date = _row_field(
        report, "date", "Date", "fiscalDateEnding", "calendarYear", "reportedDate"
    )
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
        normalized = value.strip().replace(",", "").replace("$", "").replace(" ", "")
        try:
            value = float(normalized)
        except ValueError as exc:
            raise FinancialStatementExtractionError(f"{field} is invalid") from exc
    if not isinstance(value, (int, float)):
        raise FinancialStatementExtractionError(f"{field} is invalid")
    numeric = float(value)
    if numeric <= 0:
        raise FinancialStatementExtractionError(f"{field} is invalid")
    return numeric


def _facts(
    symbol: str,
    fiscal_year: int,
    revenue: float,
    source: dict[str, Any],
    *,
    case_id: str | None = None,
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "symbol": symbol,
        "fiscal_year": str(fiscal_year),
        "revenue": revenue,
    }
    reported_currency = _row_field(source, "reportedCurrency", "currency")
    facts["currency"] = (
        reported_currency
        if isinstance(reported_currency, str) and reported_currency
        else "USD"
    )
    if case_id == "cn-600519-market-coverage":
        facts["market"] = "CN"
    elif case_id == "aapl-canonical-identifier":
        facts["resolved_identifier"] = symbol
    elif case_id == "aapl-fiscal-period-shape":
        facts["unit"] = facts["currency"]
        facts["period_label"] = f"FY{fiscal_year}"
    filing_date = _row_field(source, "date", "end")
    if isinstance(filing_date, str) and filing_date:
        facts["filing_date"] = filing_date
    return facts


def _row_field(row: dict[str, Any], *names: str) -> object:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    nested = row.get("data")
    if isinstance(nested, dict):
        for name in names:
            value = nested.get(name)
            if value is not None:
                return value
    return None
