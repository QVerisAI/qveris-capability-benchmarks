import json
from pathlib import Path

import pytest

from qveris_bench.cap_packs.dividend_events.direct import (
    DividendDirectError,
    evaluate_dividend_document,
)
from qveris_bench.cap_packs.dividend_events.models import DividendRequestIdentity
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"


def _case(case_id: str):
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )
    return next(case for case in compiled.cases if case.case_id == case_id)


def _market_case(case_id: str):
    compiled = compile_suite(
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
    )
    return next(case for case in compiled.cases if case.case_id == case_id)


def test_ac7_missing_optional_currency_does_not_invent_a_failure() -> None:
    result = evaluate_dividend_document(
        "alpha-vantage",
        {
            "symbol": "AAPL",
            "data": [{"ex_dividend_date": "2026-05-11", "amount": "0.27"}],
        },
        _case("aapl-dividends-fixed-window"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
    )

    assert result.state is CellState.COMPLETED
    assert "currency" not in result.facts
    assert result.failure_attribution is None


def test_ac7_missing_required_event_date_is_provider_negative() -> None:
    result = evaluate_dividend_document(
        "ifind",
        [{"stock_code": "600519.SH", "cash_dividend_per_share": 28.02423}],
        _case("cn-600519-dividends-fixed-window"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
    )

    assert result.state is CellState.PROVIDER_NEGATIVE
    assert result.unmet_conditions == ("effective_date",)
    assert result.failure_attribution is FailureAttribution.EMPTY_OR_PARTIAL_DATA


def test_ac7_ifind_native_ratio_only_response_is_partial_data() -> None:
    result = evaluate_dividend_document(
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
                                        "除权除息日|年度分红比例（单位：%）|"
                                        "年度累计分红总额（单位：元）|\n"
                                        "|---|---|---|---|---|---|\n"
                                        "|600519.SH|贵州茅台|||2.99|35000000000|"
                                    ),
                                    "indicators_params": {"年度分红比例": {}},
                                },
                                ensure_ascii=False,
                            ),
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        },
        _case("cn-600519-dividends-fixed-window"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
    )

    assert result.state is CellState.PROVIDER_NEGATIVE
    assert result.unmet_conditions == ("effective_date", "amount")
    assert result.failure_attribution is FailureAttribution.EMPTY_OR_PARTIAL_DATA


def test_ac7_negative_control_distinguishes_empty_from_fabricated_rows() -> None:
    case = _case("invalid-dividend-symbol")
    empty = evaluate_dividend_document(
        "twelve-data",
        {"meta": {"symbol": "NOTASTOCK"}, "dividends": []},
        case,
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
    )
    fabricated = evaluate_dividend_document(
        "twelve-data",
        {
            "meta": {"symbol": "NOTASTOCK"},
            "dividends": [{"ex_date": "2026-05-11", "amount": 0.27}],
        },
        case,
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
    )

    assert empty.state is CellState.COMPLETED
    assert fabricated.state is CellState.PROVIDER_NEGATIVE
    assert (
        fabricated.failure_attribution is FailureAttribution.PROVIDER_VALIDATION_ERROR
    )


def test_ac7_explicit_provider_rejection_completes_the_negative_control() -> None:
    result = evaluate_dividend_document(
        "eodhd",
        {
            "result": {"status_code": 404, "data": "Symbol not found"},
            "success": False,
        },
        _case("invalid-dividend-symbol"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
    )

    assert result.state is CellState.COMPLETED
    assert result.facts == {"validation_error": "invalid symbol or no dividend events"}
    assert result.failure_attribution is None


def test_ac7_malformed_response_stays_a_benchmark_error() -> None:
    with pytest.raises(DividendDirectError, match="extract"):
        evaluate_dividend_document(
            "alpha-vantage",
            {},
            _case("aapl-dividends-fixed-window"),
            PACK / "observation-schema.yaml",
            "sha256:" + "a" * 64,
        )


def test_ac7_market_case_keeps_request_bound_identity_separate() -> None:
    result = evaluate_dividend_document(
        "eodhd",
        "Date,Dividends\n2026-05-11,0.27\n",
        _market_case("us-aapl-dividend-market"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
        request_identity=DividendRequestIdentity(
            market="US", canonical_symbol="AAPL", vendor_symbol="AAPL.US"
        ),
    )

    assert result.state is CellState.COMPLETED
    assert result.facts["identity_verified"] is True
    assert result.facts["identity_basis"] == "request_bound"
    assert "returned_symbol" not in result.facts


def test_ac7_market_case_fails_a_conflicting_returned_symbol() -> None:
    result = evaluate_dividend_document(
        "hangseng",
        {
            "data": {
                "rows": [
                    {
                        "stockobject": "1679",
                        "stockcode": "000001",
                        "exdivdate": "2026-06-26",
                        "dividendpretax": 28.02423,
                    }
                ]
            }
        },
        _market_case("cn-600519-dividend-market"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
        request_identity=DividendRequestIdentity(
            market="CN", canonical_symbol="600519.SH", vendor_symbol="600519"
        ),
    )

    assert result.state is CellState.PROVIDER_NEGATIVE
    assert result.facts["identity_verified"] is False
    assert result.facts["returned_symbol"] == "000001"
    assert result.unmet_conditions == ("identity_verified",)


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
                        "status": "error",
                        "message": "instrument requires another plan",
                    },
                }
            },
        ),
    ],
)
def test_ac7_positive_provider_rejection_is_terminal_negative_evidence(
    provider_id: str, document: object
) -> None:
    result = evaluate_dividend_document(
        provider_id,
        document,
        _market_case("jp-7203-dividend-market"),
        PACK / "observation-schema.yaml",
        "sha256:" + "a" * 64,
        request_identity=DividendRequestIdentity(
            market="JP", canonical_symbol="7203.T", vendor_symbol="7203.T"
        ),
    )

    assert result.state is CellState.PROVIDER_NEGATIVE
    assert result.facts["identity_basis"] == "request_bound"
    assert result.unmet_conditions == ("effective_date", "amount")
