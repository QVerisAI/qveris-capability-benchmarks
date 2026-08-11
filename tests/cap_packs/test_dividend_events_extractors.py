import json

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
                                "stockcode": "600519",
                                "exdivdate": "2026-06-26",
                                "dividendpretax": 28.02423,
                                "paydate": "2026-06-26",
                                "regdate": "2026-06-25",
                                "preanndate": "2026-04-17",
                            }
                        ]
                    }
                }
            },
            {
                "symbol": "600519.SH",
                "effective_date": "2026-06-26",
                "amount": 28.02423,
                "payment_date": "2026-06-26",
                "record_date": "2026-06-25",
                "declaration_date": "2026-04-17",
                "event_count": 1,
            },
        ),
        (
            "ifind",
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "code": 1,
                                "msg": "success",
                                "data": json.dumps(
                                    {
                                        "answer": (
                                            "|证券代码|证券简称|年度累计单位分红（单位：元）|"
                                            "除权除息日|\n|---|---|---|---|\n"
                                            "|600519.SH|贵州茅台|27.646|2025-06-27|"
                                        ),
                                        "indicators_params": {},
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            },
            {
                "symbol": "600519.SH",
                "effective_date": "2025-06-27",
                "amount": 27.646,
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


def test_ac5_ifind_native_markdown_does_not_infer_ratio_or_total_as_amount() -> None:
    document = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "code": 1,
                        "msg": "success",
                        "data": json.dumps(
                            {
                                "answer": (
                                    "|证券代码|证券简称|年度累计单位分红（单位：元）|"
                                    "除权除息日|年度分红比例（单位：%）|年度累计分红总额（单位：元）|\n"
                                    "|---|---|---|---|---|---|\n"
                                    "|600519.SH|贵州茅台|||2.99|35000000000|"
                                ),
                                "indicators_params": {"年度分红比例": {"年度": "2025"}},
                            },
                            ensure_ascii=False,
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    }

    assert extract_dividend_event(
        "ifind",
        document,
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2026-07-31",
    ) == {"symbol": "600519.SH"}


def test_ac5_ifind_native_empty_answer_is_an_explicit_negative() -> None:
    document = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "code": 1,
                        "msg": "success",
                        "data": json.dumps(
                            {"answer": "查询结果为空", "indicators_params": {}},
                            ensure_ascii=False,
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    }

    assert extract_dividend_event(
        "ifind",
        document,
        symbol="NOTASTOCK",
        start_date=None,
        end_date=None,
        negative_control=True,
    ) == {"validation_error": "invalid symbol or no dividend events"}


def test_ac5_hangseng_bonus_share_fields_are_not_cash_dividend_facts() -> None:
    facts = extract_dividend_event(
        "hangseng",
        {
            "data": {
                "rows": [
                    {
                        "stockcode": "600519",
                        "bonustradedate": "2026-06-26",
                        "bonuspershare": 0.1,
                    }
                ]
            }
        },
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2026-07-31",
    )

    assert facts == {"symbol": "600519.SH", "event_count": 1}


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
        (
            "hangseng",
            {
                "error_message": "tool returned no valid data",
                "result": {
                    "status_code": 200,
                    "data": {
                        "success": True,
                        "code": 0,
                        "message": "verify the request parameters",
                        "data": {},
                    },
                },
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
