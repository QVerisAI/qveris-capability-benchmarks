from __future__ import annotations

from pathlib import Path

from qveris_bench.models.enums import CellState


def request_for_cell(
    provider_id: str, access_path_id: str, case_id: str
) -> tuple[str, dict[str, str]]:
    if (provider_id, access_path_id) == ("binance", "binance-crypto-spot-qveris"):
        return "binance.ticker.24hr.retrieve.v1", {
            "symbol": (
                "BTCUSDT" if case_id == "crypto-btcusdt-spot-quote" else "NOTAPAIRXYZ"
            ),
            "type": "FULL",
        }
    if (provider_id, access_path_id) == ("okx", "okx-crypto-spot-qveris"):
        return "okx_api_v5.market.ticker.retrieve.v5.e878da46", {
            "instId": (
                "BTC-USDT" if case_id == "crypto-btcusdt-spot-quote" else "NOT-A-PAIR"
            )
        }
    raise ValueError("unfrozen Provider / Access Path")


def assert_new_release_paths(public_root: Path, release_root: Path) -> None:
    if public_root.exists() or release_root.exists():
        raise ValueError("release already exists; choose a new immutable release ID")


def assert_publishable_terminal_matrix(
    terminals: tuple[tuple[str, CellState], ...]
) -> None:
    for case_id, state in terminals:
        if case_id == "crypto-btcusdt-spot-quote":
            expected = CellState.COMPLETED
        elif case_id == "crypto-invalid-spot-symbol":
            expected = CellState.PROVIDER_NEGATIVE
        else:
            raise ValueError("unfrozen case cannot be published")
        if state is not expected:
            label = "positive" if expected is CellState.COMPLETED else "negative"
            raise ValueError(f"{label} case did not meet its publication outcome")
