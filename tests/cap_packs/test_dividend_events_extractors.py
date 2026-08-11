import pytest

from qveris_bench.cap_packs.dividend_events.extractors import (
    DividendExtractionError,
    extract_dividend_event,
)


@pytest.mark.parametrize(
    ("provider_id", "document", "expected"),
    [
        (
            "twelve-data",
            {
                "meta": {"symbol": "AAPL", "currency": "USD"},
                "dividends": [
                    {"ex_date": "2026-05-11", "amount": 0.27},
                    {"ex_date": "2026-02-09", "amount": 0.26},
                ],
            },
            {
                "symbol": "AAPL",
                "effective_date": "2026-05-11",
                "amount": 0.27,
                "currency": "USD",
                "event_count": 2,
            },
        ),
        (
            "massive-stocks",
            {
                "results": [
                    {
                        "ticker": "AAPL",
                        "ex_dividend_date": "2026-05-11",
                        "cash_amount": 0.27,
                        "currency": "USD",
                        "pay_date": "2026-05-14",
                        "declaration_date": "2026-04-30",
                        "record_date": "2026-05-11",
                    }
                ]
            },
            {
                "symbol": "AAPL",
                "effective_date": "2026-05-11",
                "amount": 0.27,
                "currency": "USD",
                "payment_date": "2026-05-14",
                "declaration_date": "2026-04-30",
                "record_date": "2026-05-11",
                "event_count": 1,
            },
        ),
        (
            "alpha-vantage",
            {
                "symbol": "AAPL",
                "data": [
                    {
                        "ex_dividend_date": "2026-05-11",
                        "amount": "0.27",
                        "payment_date": "2026-05-14",
                    }
                ],
            },
            {
                "symbol": "AAPL",
                "effective_date": "2026-05-11",
                "amount": 0.27,
                "payment_date": "2026-05-14",
                "event_count": 1,
            },
        ),
        (
            "eodhd",
            "Date,Dividends\n2026-02-09,0.26\n2026-05-11,0.27\n",
            {
                "symbol": "AAPL",
                "effective_date": "2026-05-11",
                "amount": 0.27,
                "event_count": 2,
            },
        ),
        (
            "hangseng",
            {
                "data": {
                    "data": {
                        "rows": [
                            {
                                "stockobject": "600519.SH",
                                "bonustradedate": "2024-06-26",
                                "bonuspershare": 30.876,
                                "preanndate": "2024-04-02",
                            }
                        ]
                    }
                }
            },
            {
                "symbol": "600519.SH",
                "effective_date": "2024-06-26",
                "amount": 30.876,
                "declaration_date": "2024-04-02",
                "event_count": 1,
            },
        ),
        (
            "ifind",
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"data":[{"stock_code":"600519.SH",'
                            '"ex_dividend_date":"2025-06-27",'
                            '"cash_dividend_per_share":27.646,"currency":"CNY"}]}'
                        ),
                    }
                ]
            },
            {
                "symbol": "600519.SH",
                "effective_date": "2025-06-27",
                "amount": 27.646,
                "currency": "CNY",
                "event_count": 1,
            },
        ),
    ],
)
def test_ac5_extractors_normalize_latest_dividend_event(
    provider_id: str, document: object, expected: dict[str, object]
) -> None:
    assert (
        extract_dividend_event(
            provider_id,
            document,
            symbol="600519.SH" if provider_id in {"ifind", "hangseng"} else "AAPL",
            start_date="2024-01-01",
            end_date="2026-07-31",
        )
        == expected
    )


def test_ac5_missing_optional_currency_stays_unavailable() -> None:
    facts = extract_dividend_event(
        "alpha-vantage",
        {
            "symbol": "AAPL",
            "data": [{"ex_dividend_date": "2026-05-11", "amount": "0.27"}],
        },
        symbol="AAPL",
        start_date="2024-01-01",
        end_date="2026-07-31",
    )

    assert "currency" not in facts


def test_ac5_missing_required_date_produces_partial_facts() -> None:
    facts = extract_dividend_event(
        "ifind",
        [{"stock_code": "600519.SH", "cash_dividend_per_share": 28.02423}],
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2026-07-31",
    )

    assert facts == {"symbol": "600519.SH", "amount": 28.02423, "event_count": 1}


def test_ac5_negative_control_requires_an_explicit_empty_result() -> None:
    assert extract_dividend_event(
        "twelve-data",
        {"meta": {"symbol": "NOTASTOCK"}, "dividends": []},
        symbol="NOTASTOCK",
        start_date=None,
        end_date=None,
        negative_control=True,
    ) == {"validation_error": "invalid symbol or no dividend events"}

    with pytest.raises(DividendExtractionError, match="negative control returned"):
        extract_dividend_event(
            "twelve-data",
            {
                "meta": {"symbol": "NOTASTOCK"},
                "dividends": [{"ex_date": "2026-05-11", "amount": 0.27}],
            },
            symbol="NOTASTOCK",
            start_date=None,
            end_date=None,
            negative_control=True,
        )


@pytest.mark.parametrize(
    ("provider_id", "document"),
    [
        (
            "eodhd",
            {
                "result": {"status_code": 404, "data": "Symbol not found"},
                "success": False,
            },
        ),
        (
            "twelve-data",
            {
                "result": {
                    "status_code": 4042,
                    "data": {
                        "code": 404,
                        "message": "symbol parameter is invalid",
                        "status": "error",
                    },
                }
            },
        ),
        (
            "hangseng",
            {
                "result": {
                    "status_code": 200,
                    "data": {
                        "success": True,
                        "code": 0,
                        "data": {
                            "msg": "invalid stock code",
                            "code": "500",
                            "data": {},
                        },
                    },
                }
            },
        ),
    ],
)
def test_ac5_negative_control_accepts_explicit_provider_rejection(
    provider_id: str, document: object
) -> None:
    assert extract_dividend_event(
        provider_id,
        document,
        symbol="NOTASTOCK",
        start_date=None,
        end_date=None,
        negative_control=True,
    ) == {"validation_error": "invalid symbol or no dividend events"}


def test_ac5_negative_control_rejects_an_unknown_malformed_response() -> None:
    with pytest.raises(DividendExtractionError):
        extract_dividend_event(
            "twelve-data",
            {"message": "unknown response"},
            symbol="NOTASTOCK",
            start_date=None,
            end_date=None,
            negative_control=True,
        )
