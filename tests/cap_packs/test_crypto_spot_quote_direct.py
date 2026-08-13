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


def test_missing_ohlc_or_wrong_symbol_cannot_complete() -> None:
    terminal = evaluate(
        "binance",
        "crypto-btcusdt-spot-quote",
        {"status_code": 200, "data": {"symbol": "ETHUSDT", "lastPrice": "10"}},
    )
    assert terminal.state is CellState.PROVIDER_NEGATIVE
    assert terminal.attribution is FailureAttribution.EMPTY_OR_PARTIAL_DATA
