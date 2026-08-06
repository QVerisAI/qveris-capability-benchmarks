import pytest

from qveris_bench.outcomes.etf_holdings import (
    EtfHoldingsExtractionError,
    extract_alpha_vantage_etf_holdings,
)


def test_ac_alpha_vantage_positive_response_becomes_weighted_observation() -> None:
    facts = extract_alpha_vantage_etf_holdings(
        {
            "result": {
                "data": {
                    "holdings": [
                        {"symbol": "AAPL", "weight": "7.25%"},
                        {"symbol": "MSFT", "weight": 0.061},
                    ]
                }
            }
        },
        "SPY",
    )

    assert facts == {
        "symbol": "SPY",
        "holdings": ["AAPL", "MSFT"],
        "weights": [0.0725, 0.061],
    }


def test_ac_alpha_vantage_negative_empty_holdings_is_a_validation_fact() -> None:
    assert extract_alpha_vantage_etf_holdings(
        {"result": {"data": {}, "error": {"code": "invalid_symbol"}}},
        "NOTANETF",
        negative_control=True,
    ) == {"validation_error": "provider returned explicit validation response"}


@pytest.mark.parametrize(
    "error",
    [
        {"code": "rate_limited"},
        {"code": "authentication_failed"},
        {"code": "internal_error"},
        "rate limited",
    ],
)
def test_ac_alpha_vantage_negative_rejects_non_validation_errors(
    error: object,
) -> None:
    with pytest.raises(EtfHoldingsExtractionError, match="validation error"):
        extract_alpha_vantage_etf_holdings(
            {"result": {"data": {}, "error": error}},
            "NOTANETF",
            negative_control=True,
        )


def test_ac_alpha_vantage_negative_top_level_invalid_symbol_message_is_a_fact() -> None:
    assert extract_alpha_vantage_etf_holdings(
        {
            "error_message": "NOTANETF is an invalid ETF symbol",
            "result": {"data": {}},
        },
        "NOTANETF",
        negative_control=True,
    ) == {"validation_error": "provider returned explicit validation response"}


def test_ac_alpha_vantage_negative_top_level_runtime_message_is_rejected() -> None:
    with pytest.raises(EtfHoldingsExtractionError, match="validation error"):
        extract_alpha_vantage_etf_holdings(
            {
                "error_message": "rate limit exceeded",
                "result": {"data": {}},
            },
            "NOTANETF",
            negative_control=True,
        )


def test_ac_alpha_vantage_negative_rejects_invalid_api_key_message() -> None:
    with pytest.raises(EtfHoldingsExtractionError, match="validation error"):
        extract_alpha_vantage_etf_holdings(
            {
                "error_message": "invalid API key for ETF endpoint",
                "result": {"data": {}},
            },
            "NOTANETF",
            negative_control=True,
        )


def test_ac_alpha_vantage_negative_empty_data_without_error_is_rejected() -> None:
    with pytest.raises(EtfHoldingsExtractionError, match="validation error"):
        extract_alpha_vantage_etf_holdings(
            {"result": {"data": {}}}, "NOTANETF", negative_control=True
        )


def test_ac_alpha_vantage_rejects_unmarked_percentages() -> None:
    with pytest.raises(EtfHoldingsExtractionError, match="weight"):
        extract_alpha_vantage_etf_holdings(
            {"result": {"data": {"holdings": [{"symbol": "AAPL", "weight": 7.25}]}}},
            "SPY",
        )


def test_ac_alpha_vantage_rejects_non_object_responses() -> None:
    with pytest.raises(EtfHoldingsExtractionError, match="response must be an object"):
        extract_alpha_vantage_etf_holdings([], "SPY")
