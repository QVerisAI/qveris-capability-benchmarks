from __future__ import annotations

import time
from pathlib import Path

import pytest

from qveris_bench.cap_packs.stock_quote_family.extractors import (
    StockQuoteExtractionError,
    extract_eodhd_stock_quote,
    extract_finnhub_stock_quote,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/stock_quote_family"
DIGEST = "sha256:" + "a" * 64


def _finnhub_quote(price: float, timestamp: int) -> dict[str, object]:
    return {
        "result": {
            "data": {
                "c": price,
                "d": 0.1,
                "dp": 0.04,
                "h": price + 1,
                "l": price - 1,
                "o": price,
                "pc": price - 0.05,
                "t": timestamp,
            }
        }
    }


def _finnhub_unavailable() -> dict[str, object]:
    return {
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
    }


def test_ac5_finnhub_positive_extracts_symbol_price_and_timestamp() -> None:
    document = _finnhub_quote(223.18, int(time.time()))

    facts = extract_finnhub_stock_quote(document, "AAPL")
    observation = extract_observation(
        PACK / "observation-schema.yaml", facts, DIGEST, "1.0.0"
    )

    assert observation.facts["symbol"] == "AAPL"
    assert observation.facts["price"] == 223.18
    assert observation.facts["timestamp"]


def test_ac5_finnhub_negative_returns_validation_error() -> None:
    facts = extract_finnhub_stock_quote(
        _finnhub_unavailable(), "NOTASTOCK", negative_control=True
    )

    assert facts == {"validation_error": "provider returned an unavailable quote"}


def test_ac5_finnhub_cn_symbol_is_explicitly_unavailable() -> None:
    with pytest.raises(StockQuoteExtractionError, match="unavailable"):
        extract_finnhub_stock_quote(_finnhub_unavailable(), "600519.SH")


def test_ac5_finnhub_freshness_facts_carry_provider_currency_when_present() -> None:
    document = _finnhub_quote(223.18, int(time.time()))
    document["result"]["data"]["currency"] = "USD"

    facts = extract_finnhub_stock_quote(document, "AAPL")

    assert facts["currency"] == "USD"
    extract_observation(PACK / "observation-schema.yaml", facts, DIGEST, "1.0.0")


def test_ac5_coverage_facts_carry_provider_market_when_present() -> None:
    document = _finnhub_quote(223.18, int(time.time()))
    document["result"]["data"]["market"] = "XNAS"

    facts = extract_finnhub_stock_quote(document, "600519.SH")

    assert facts["market"] == "XNAS"


def test_ac5_eodhd_positive_extracts_quote_facts() -> None:
    document = {
        "result": {
            "data": {
                "data": {
                    "AAPL.US": {
                        "lastTradePrice": 223.18,
                        "lastTradeTime": int(time.time()) * 1000,
                    }
                }
            }
        }
    }

    facts = extract_eodhd_stock_quote(document, "AAPL")
    observation = extract_observation(
        PACK / "observation-schema.yaml", facts, DIGEST, "1.0.0"
    )

    assert observation.facts["price"] == 223.18


def test_ac5_eodhd_negative_returns_validation_error() -> None:
    document = {
        "error_message": "Unknown symbol. You have entered NOTASTOCK.US",
        "result": {"data": {"data": []}},
    }

    facts = extract_eodhd_stock_quote(document, "NOTASTOCK", negative_control=True)

    assert facts == {
        "validation_error": "provider returned explicit validation response"
    }


def test_ac5_eodhd_cn_symbol_is_explicitly_unavailable() -> None:
    document = {
        "error_message": "Unknown symbol. You have entered 600519.SH",
        "result": {"data": {"data": []}},
    }

    with pytest.raises(StockQuoteExtractionError, match="unavailable"):
        extract_eodhd_stock_quote(document, "600519.SH")


def test_ac5_observation_schema_rejects_missing_price() -> None:
    with pytest.raises(ExtractionError, match="price"):
        extract_observation(
            PACK / "observation-schema.yaml",
            {"symbol": "AAPL", "timestamp": "2026-08-07T00:00:00+00:00"},
            DIGEST,
            "1.0.0",
        )
