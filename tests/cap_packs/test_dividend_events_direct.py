from pathlib import Path

import pytest

from qveris_bench.cap_packs.dividend_events.direct import (
    DividendDirectError,
    evaluate_dividend_document,
)
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"


def _case(case_id: str):
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
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
        fabricated.failure_attribution
        is FailureAttribution.PROVIDER_VALIDATION_ERROR
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
