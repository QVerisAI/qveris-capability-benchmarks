from __future__ import annotations

from pathlib import Path

import pytest

from qveris_bench.cap_packs.crypto_spot_quote.extractors import (
    CryptoSpotQuoteExtractionError,
    extract_binance_quote,
    extract_okx_quote,
)
from qveris_bench.cap_packs.crypto_spot_quote.runner import (
    assert_new_release_paths,
    assert_publishable_terminal_matrix,
    request_for_cell,
)
from qveris_bench.models.enums import CellState


def test_binance_extractor_maps_the_harbor_required_fields() -> None:
    facts = extract_binance_quote(
        {
            "symbol": "BTCUSDT",
            "lastPrice": "63815.76",
            "openPrice": "63632.52",
            "highPrice": "64500.00",
            "lowPrice": "63310.34",
            "closeTime": 1786602404007,
        },
        expected_symbol="BTCUSDT",
    )

    assert facts == {
        "symbol": "BTCUSDT",
        "price": 63815.76,
        "open": 63632.52,
        "high": 64500.0,
        "low": 63310.34,
        "timestamp": 1786602404007,
        "exchange": "BINANCE",
        "currency": "USDT",
    }


def test_okx_extractor_maps_the_vendor_symbol_to_the_canonical_symbol() -> None:
    facts = extract_okx_quote(
        {
            "code": "0",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": "BTC-USDT",
                    "last": "63820.2",
                    "open24h": "63616.1",
                    "high24h": "64496.9",
                    "low24h": "63309.4",
                    "ts": "1786602616166",
                }
            ],
        },
        expected_symbol="BTCUSDT",
    )

    assert facts == {
        "symbol": "BTCUSDT",
        "price": 63820.2,
        "open": 63616.1,
        "high": 64496.9,
        "low": 63309.4,
        "timestamp": 1786602616166,
        "exchange": "OKX",
        "currency": "USDT",
    }


def test_extractor_rejects_a_mismatched_or_incomplete_response() -> None:
    try:
        extract_binance_quote(
            {"symbol": "ETHUSDT", "lastPrice": "1"}, expected_symbol="BTCUSDT"
        )
    except CryptoSpotQuoteExtractionError as exc:
        assert "symbol" in str(exc)
    else:
        raise AssertionError("mismatched response must not become a quote fact")


def test_runner_binds_each_request_to_its_access_path() -> None:
    tool_id, parameters = request_for_cell(
        "binance", "binance-crypto-spot-qveris", "crypto-btcusdt-spot-quote"
    )
    assert tool_id == "binance.ticker.24hr.retrieve.v1"
    assert parameters == {"symbol": "BTCUSDT", "type": "FULL"}
    with pytest.raises(ValueError, match="unfrozen Provider / Access Path"):
        request_for_cell(
            "binance", "okx-crypto-spot-qveris", "crypto-btcusdt-spot-quote"
        )


def test_runner_refuses_to_overwrite_an_existing_release(tmp_path: Path) -> None:
    public_root = tmp_path / "evidence"
    release_root = tmp_path / "release"
    public_root.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        assert_new_release_paths(public_root, release_root)


def test_runner_rejects_a_release_when_a_positive_sample_is_not_complete() -> None:
    with pytest.raises(ValueError, match="positive"):
        assert_publishable_terminal_matrix(
            (("crypto-btcusdt-spot-quote", CellState.INFRA_BLOCKED),)
        )


def test_runner_rejects_an_unfrozen_case() -> None:
    with pytest.raises(ValueError, match="unfrozen case"):
        assert_publishable_terminal_matrix((("unexpected-case", CellState.COMPLETED),))
