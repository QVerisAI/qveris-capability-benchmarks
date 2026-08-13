from __future__ import annotations


def request_for_cell(provider_id: str, case_id: str) -> tuple[str, dict[str, str]]:
    if provider_id == "binance":
        return "binance.ticker.24hr.retrieve.v1", {
            "symbol": (
                "BTCUSDT"
                if case_id == "crypto-btcusdt-spot-quote"
                else "NOTAPAIRXYZ"
            ),
            "type": "FULL",
        }
    if provider_id == "okx":
        return "okx_api_v5.market.ticker.retrieve.v5.e878da46", {
            "instId": (
                "BTC-USDT"
                if case_id == "crypto-btcusdt-spot-quote"
                else "NOT-A-PAIR"
            )
        }
    raise ValueError("unfrozen Provider / Access Path")
