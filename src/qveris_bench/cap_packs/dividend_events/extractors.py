from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

from qveris_bench.cap_packs.dividend_events.models import DividendRequestIdentity


class DividendExtractionError(ValueError):
    pass


class DividendNegativeControlError(DividendExtractionError):
    pass


_SYMBOL_FIELDS = (
    "symbol",
    "ticker",
    "stockcode",
    "stock_code",
    "stockobject",
)
_DATE_FIELDS = (
    "effective_date",
    "ex_date",
    "ex_dividend_date",
    "date",
    "Date",
    "exdivdate",
    "dividend_date",
)
_AMOUNT_FIELDS = (
    "amount",
    "cash_amount",
    "Dividends",
    "dividendpretax",
    "cash_dividend_per_share",
)


def extract_dividend_event(
    provider_id: str,
    document: object,
    *,
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    negative_control: bool = False,
    request_identity: DividendRequestIdentity | None = None,
) -> dict[str, Any]:
    normalized = _unwrap_gateway(document)
    if _is_explicit_provider_rejection(provider_id, document, normalized):
        if negative_control:
            return {"validation_error": "invalid symbol or no dividend events"}
        return _identity_facts(symbol, None, request_identity)
    rows, metadata = _provider_rows(provider_id, normalized)
    if negative_control:
        if rows:
            raise DividendNegativeControlError(
                "negative control returned dividend events"
            )
        return {"validation_error": "invalid symbol or no dividend events"}

    selected_rows = _within_window(rows, start_date, end_date)
    if not selected_rows:
        return _identity_facts(symbol, None, request_identity)
    selected = max(selected_rows, key=lambda row: _date_value(row) or "")
    returned_symbol = _string_field(selected, _SYMBOL_FIELDS) or _string_field(
        metadata, _SYMBOL_FIELDS
    )
    facts = _identity_facts(symbol, returned_symbol, request_identity)
    facts["event_count"] = len(selected_rows)
    effective_date = _date_value(selected)
    if effective_date is not None:
        facts["effective_date"] = effective_date
    amount = _number_field(selected, _AMOUNT_FIELDS)
    if amount is not None:
        facts["amount"] = amount
    currency = _string_field(selected, ("currency",)) or _string_field(
        metadata, ("currency",)
    )
    if currency is not None:
        facts["currency"] = currency
    for output, aliases in (
        ("payment_date", ("payment_date", "pay_date", "paydate")),
        ("declaration_date", ("declaration_date", "preanndate")),
        ("record_date", ("record_date", "regdate")),
    ):
        value = _normalized_date(_field(selected, aliases))
        if value is not None:
            facts[output] = value
    return facts


def _canonical_symbol(returned_symbol: str | None, requested_symbol: str) -> str:
    if returned_symbol is None:
        return requested_symbol
    returned = returned_symbol.strip().upper()
    requested = requested_symbol.strip().upper()
    if returned == requested or returned.split(".", 1)[0] == requested.split(".", 1)[0]:
        return requested_symbol
    return returned_symbol


def _identity_facts(
    requested_symbol: str,
    returned_symbol: str | None,
    request_identity: DividendRequestIdentity | None,
) -> dict[str, Any]:
    if request_identity is None:
        return {"symbol": _canonical_symbol(returned_symbol, requested_symbol)}
    matches = returned_symbol is None or _symbol_base(returned_symbol) in {
        _symbol_base(request_identity.vendor_symbol),
        _symbol_base(request_identity.canonical_symbol),
    }
    facts: dict[str, Any] = {
        "symbol": (
            request_identity.canonical_symbol if matches else str(returned_symbol)
        ),
        "identity_verified": matches,
        "identity_basis": (
            "request_bound" if returned_symbol is None else "response_field"
        ),
    }
    if returned_symbol is not None:
        facts["returned_symbol"] = returned_symbol
    return facts


def _symbol_base(value: str) -> str:
    return value.strip().upper().split(":", 1)[0].split(".", 1)[0]


def _unwrap_gateway(document: object) -> object:
    if not isinstance(document, dict):
        return document
    result = document.get("result")
    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return document


def _is_explicit_provider_rejection(
    provider_id: str, document: object, normalized: object
) -> bool:
    if provider_id == "ifind":
        try:
            data = _ifind_data(_unwrap_mcp_content(normalized))
        except DividendExtractionError:
            return False
        return (
            data["answer"].strip() == "查询结果为空" and not data["indicators_params"]
        )
    if provider_id == "eodhd":
        return _gateway_status(document) >= 400 and isinstance(normalized, str)
    if provider_id == "twelve-data":
        if _gateway_status(document) < 400 or not isinstance(normalized, dict):
            return False
        return normalized.get("status") == "error" and isinstance(
            normalized.get("message"), str
        )
    if provider_id == "hangseng" and isinstance(normalized, dict):
        if (
            _gateway_status(document) == 200
            and isinstance(document, dict)
            and isinstance(document.get("error_message"), str)
            and normalized.get("success") is True
            and _integer_code(normalized.get("code")) == 0
            and isinstance(normalized.get("message"), str)
            and normalized.get("data") == {}
        ):
            return True
        inner = normalized.get("data")
        if not isinstance(inner, dict):
            return False
        code = _integer_code(inner.get("code"))
        return (
            code is not None
            and code >= 400
            and isinstance(inner.get("msg"), str)
            and inner.get("data") == {}
        )
    return False


def _gateway_status(document: object) -> int:
    if not isinstance(document, dict):
        return 0
    result = document.get("result")
    if not isinstance(result, dict):
        return 0
    return _integer_code(result.get("status_code")) or 0


def _integer_code(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _provider_rows(
    provider_id: str, document: object
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if provider_id == "eodhd":
        return _csv_rows(document), {}
    if provider_id == "twelve-data":
        data = _mapping(document)
        return _required_rows(data, "dividends"), _mapping(data.get("meta", {}))
    if provider_id == "massive-stocks":
        data = _mapping(document)
        return _required_rows(data, "results"), data
    if provider_id == "alpha-vantage":
        data = _mapping(document)
        return _required_rows(data, "data"), data
    if provider_id == "hangseng":
        data = _mapping(document)
        rows = _find_rows(data, "rows")
        if rows is None:
            raise DividendExtractionError("Hangseng dividend rows are missing")
        return rows, data
    if provider_id == "ifind":
        payload = _unwrap_mcp_content(document)
        if isinstance(payload, list):
            return _dict_rows(payload), {}
        data = _ifind_data(payload)
        return _ifind_dividend_rows(data["answer"]), {}
    raise DividendExtractionError(f"unsupported dividend provider: {provider_id}")


def _csv_rows(document: object) -> list[dict[str, Any]]:
    if not isinstance(document, str):
        raise DividendExtractionError("EODHD dividend response must be CSV")
    reader = csv.DictReader(StringIO(document))
    if not reader.fieldnames or not {"Date", "Dividends"}.issubset(reader.fieldnames):
        raise DividendExtractionError("EODHD dividend columns are missing")
    return _dict_rows(list(reader))


def _unwrap_mcp_content(document: object) -> object:
    if not isinstance(document, dict) or not isinstance(document.get("content"), list):
        return document
    texts: list[str] = []
    for item in document["content"]:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"])
    for text in texts:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue
    raise DividendExtractionError("iFind MCP response has no structured dividend data")


def _ifind_data(payload: object) -> dict[str, Any]:
    outer = _mapping(payload)
    raw_data = outer.get("data")
    if not isinstance(raw_data, str):
        raise DividendExtractionError("iFind MCP data must be a JSON string")
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as error:
        raise DividendExtractionError("iFind MCP data is not valid JSON") from error
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("answer"), str)
        or not isinstance(data.get("indicators_params"), dict)
    ):
        raise DividendExtractionError("iFind MCP dividend fields are missing")
    return data


def _ifind_dividend_rows(answer: str) -> list[dict[str, Any]]:
    required_headers = {
        "证券代码",
        "年度累计单位分红（单位：元）",
        "除权除息日",
    }
    rows: list[dict[str, Any]] = []
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    index = 0
    while index + 1 < len(lines):
        headers = _markdown_cells(lines[index])
        separator = _markdown_cells(lines[index + 1])
        if not required_headers.issubset(headers) or not _is_markdown_separator(
            separator
        ):
            index += 1
            continue
        index += 2
        while index < len(lines):
            values = _markdown_cells(lines[index])
            if len(values) != len(headers) or _is_markdown_separator(values):
                break
            row = dict(zip(headers, values, strict=True))
            effective_date = row["除权除息日"].strip()
            amount = row["年度累计单位分红（单位：元）"].strip()
            if effective_date or amount:
                rows.append(
                    {
                        "stock_code": row["证券代码"],
                        "ex_dividend_date": effective_date,
                        "cash_dividend_per_share": amount,
                    }
                )
            index += 1
    return rows


def _markdown_cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip() for cell in line[1:-1].split("|")]


def _is_markdown_separator(cells: list[str]) -> bool:
    return bool(cells) and all(cell and not cell.strip("-:") for cell in cells)


def _required_rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list):
        raise DividendExtractionError(f"dividend {key} are missing")
    return _dict_rows(value)


def _find_rows(value: object, key: str) -> list[dict[str, Any]] | None:
    if not isinstance(value, dict):
        return None
    candidate = value.get(key)
    if isinstance(candidate, list):
        return _dict_rows(candidate)
    for nested in value.values():
        found = _find_rows(nested, key)
        if found is not None:
            return found
    return None


def _dict_rows(rows: list[object]) -> list[dict[str, Any]]:
    if not all(isinstance(row, dict) for row in rows):
        raise DividendExtractionError("dividend rows must contain objects")
    return [dict(row) for row in rows if isinstance(row, dict)]


def _within_window(
    rows: list[dict[str, Any]], start_date: str | None, end_date: str | None
) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        event_date = _date_value(row)
        if event_date is None:
            selected.append(row)
            continue
        if start_date is not None and event_date < start_date:
            continue
        if end_date is not None and event_date > end_date:
            continue
        selected.append(row)
    return selected


def _date_value(row: dict[str, Any]) -> str | None:
    return _normalized_date(_field(row, _DATE_FIELDS))


def _normalized_date(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if len(normalized) == 8 and normalized.isdigit():
        normalized = f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
    if (
        len(normalized) != 10
        or normalized[4] != "-"
        or normalized[7] != "-"
        or not normalized.replace("-", "").isdigit()
    ):
        return None
    return normalized


def _number_field(row: dict[str, Any], names: tuple[str, ...]) -> float | None:
    value = _field(row, names)
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip().replace(",", ""))
        except ValueError:
            return None
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def _string_field(row: dict[str, Any], names: tuple[str, ...]) -> str | None:
    value = _field(row, names)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _field(row: dict[str, Any], names: tuple[str, ...]) -> object:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return None


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DividendExtractionError("dividend response must be an object")
    return value
