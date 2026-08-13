from __future__ import annotations

from qveris_bench.cap_packs.crypto_spot_quote.direct import evaluate
from qveris_bench.models.enums import CellState, FailureAttribution


def test_binance_required_fields_complete_the_positive_case() -> None:
    terminal = evaluate(
        "binance",
        "crypto-btcusdt-spot-quote",
        {
            "status_code": 200,
            "data": {
                "symbol": "BTCUSDT",
                "lastPrice": "10",
                "openPrice": "9",
                "highPrice": "11",
                "lowPrice": "8",
                "closeTime": 1,
            },
        },
    )
    assert terminal.state is CellState.COMPLETED
    assert terminal.facts["symbol"] == "BTCUSDT"


def test_okx_http_success_error_payload_is_a_negative_control() -> None:
    terminal = evaluate(
        "okx",
        "crypto-invalid-spot-symbol",
        {"status_code": 200, "data": {"code": "51001", "data": []}},
    )
    assert terminal.state is CellState.PROVIDER_NEGATIVE
    assert terminal.attribution is FailureAttribution.PROVIDER_VALIDATION_ERROR


def test_binance_explicit_invalid_symbol_error_is_a_negative_control() -> None:
    terminal = evaluate(
        "binance",
        "crypto-invalid-spot-symbol",
        {
            "status_code": 400,
            "data": {"code": -1121, "msg": "Invalid symbol."},
        },
    )
    assert terminal.state is CellState.PROVIDER_NEGATIVE
    assert terminal.attribution is FailureAttribution.PROVIDER_VALIDATION_ERROR


def test_transport_or_valid_quote_cannot_complete_an_invalid_control() -> None:
    for payload in (
        {"status_code": 401, "data": {"code": -2015}},
        {"status_code": 429, "data": {"code": -1003}},
        {"status_code": 500, "data": {"error": "upstream failure"}},
        {"status_code": 200, "data": {"symbol": "BTCUSDT", "lastPrice": "10"}},
    ):
        terminal = evaluate("binance", "crypto-invalid-spot-symbol", payload)
        assert terminal.state is CellState.INFRA_BLOCKED


def test_missing_ohlc_or_wrong_symbol_blocks_publication() -> None:
    terminal = evaluate(
        "binance",
        "crypto-btcusdt-spot-quote",
        {"status_code": 200, "data": {"symbol": "ETHUSDT", "lastPrice": "10"}},
    )
    assert terminal.state is CellState.INFRA_BLOCKED
    assert terminal.attribution is FailureAttribution.EMPTY_OR_PARTIAL_DATA
