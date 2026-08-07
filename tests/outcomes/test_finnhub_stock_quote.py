from datetime import UTC, datetime

import pytest

from qveris_bench.cap_packs.stock_quote_smoke.extractors import (
    StockQuoteExtractionError,
    extract_eodhd_stock_quote,
    extract_finnhub_stock_quote,
)


def test_ac_finnhub_positive_quote_becomes_current_observation() -> None:
    facts = extract_finnhub_stock_quote(
        {"result": {"data": {"c": 201.0, "t": 1_700_000_000}}}, "AAPL"
    )

    assert facts == {
        "symbol": "AAPL",
        "price": 201.0,
        "timestamp": datetime.fromtimestamp(1_700_000_000, UTC).isoformat(),
    }


def test_ac_eodhd_live_v2_quote_becomes_current_observation() -> None:
    facts = extract_eodhd_stock_quote(
        {
            "result": {
                "data": {
                    "data": {
                        "AAPL.US": {
                            "symbol": "AAPL.US",
                            "lastTradePrice": 201.0,
                            "lastTradeTime": 1_700_000_000_000,
                        }
                    }
                }
            }
        },
        "AAPL",
    )

    assert facts == {
        "symbol": "AAPL",
        "price": 201.0,
        "timestamp": datetime.fromtimestamp(1_700_000_000, UTC).isoformat(),
    }


def test_ac_eodhd_live_v2_empty_data_with_error_becomes_validation_fact() -> None:
    assert extract_eodhd_stock_quote(
        {
            "error_message": "Unknown symbol",
            "result": {"data": {"data": []}},
        },
        "NOTASTOCK",
        negative_control=True,
    ) == {"validation_error": "provider returned explicit validation response"}


def test_ac_finnhub_invalid_symbol_quote_becomes_validation_fact() -> None:
    assert extract_finnhub_stock_quote(
        {
            "result": {
                "data": {
                    "c": 0,
                    "d": None,
                    "dp": None,
                    "h": 0,
                    "l": 0,
                    "o": 0,
                    "pc": 0,
                    "t": 0,
                }
            }
        },
        "NOTASTOCK",
        negative_control=True,
    ) == {"validation_error": "provider returned an unavailable quote"}


@pytest.mark.parametrize(
    "document",
    [
        {"result": {"data": {"c": 0, "t": 1_700_000_000}}},
        {"result": {"data": {"c": 201.0, "t": 0}}},
        {"result": {"data": {"c": "201", "t": 1_700_000_000}}},
        {"result": {"data": {"c": 201.0, "t": "1700000000"}}},
    ],
)
def test_ac_finnhub_quote_rejects_malformed_or_unavailable_positive_data(
    document: object,
) -> None:
    with pytest.raises(StockQuoteExtractionError):
        extract_finnhub_stock_quote(document, "AAPL")


def test_ac_finnhub_negative_rejects_ambiguous_or_runtime_responses() -> None:
    with pytest.raises(StockQuoteExtractionError, match="unavailable quote"):
        extract_finnhub_stock_quote(
            {"result": {"data": {"c": 0, "t": 1_700_000_000}}},
            "NOTASTOCK",
            negative_control=True,
        )


def test_ac_finnhub_negative_rejects_boolean_unavailable_envelope() -> None:
    with pytest.raises(StockQuoteExtractionError, match="unavailable quote"):
        extract_finnhub_stock_quote(
            {
                "result": {
                    "data": {
                        "c": False,
                        "d": None,
                        "dp": None,
                        "h": False,
                        "l": False,
                        "o": False,
                        "pc": False,
                        "t": False,
                    }
                }
            },
            "NOTASTOCK",
            negative_control=True,
        )


def test_ac_finnhub_quote_normalizes_out_of_range_timestamp_errors() -> None:
    with pytest.raises(StockQuoteExtractionError, match="timestamp"):
        extract_finnhub_stock_quote(
            {"result": {"data": {"c": 201.0, "t": 10**100}}}, "AAPL"
        )


def test_ac_finnhub_quote_rejects_huge_numeric_values_as_domain_errors() -> None:
    with pytest.raises(StockQuoteExtractionError, match="price"):
        extract_finnhub_stock_quote(
            {"result": {"data": {"c": 10**1000, "t": 1_700_000_000}}}, "AAPL"
        )
    with pytest.raises(StockQuoteExtractionError, match="timestamp"):
        extract_finnhub_stock_quote(
            {"result": {"data": {"c": 201.0, "t": 10**1000}}}, "AAPL"
        )
