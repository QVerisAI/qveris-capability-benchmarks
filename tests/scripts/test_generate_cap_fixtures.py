"""Acceptance tests for the Harbor contract fixture generator."""

from __future__ import annotations

from pathlib import Path

from scripts.generate_cap_fixtures import (
    load_contracts,
    render_direct_test,
    render_param_fill,
    render_self_description,
)


def _dividends_contract() -> dict:
    contracts = load_contracts(
        Path(__file__).resolve().parents[2]
        / "testdata"
        / "harbor-contracts-sample.json"
    )
    return contracts["MKT.DIVIDENDS"]


def test_direct_test_derives_required_fields() -> None:
    contract = _dividends_contract()
    out = render_direct_test(contract, "dividends")
    assert "dividends-positive" in out
    assert "negative_control: false" in out
    assert "negative_control: true" in out
    # field_spec.required drives expected_observations
    assert '"symbol"' in out
    assert '"effective_date"' in out
    assert '"amount"' in out


def test_param_fill_uses_standard_query() -> None:
    contract = _dividends_contract()
    out = render_param_fill(contract, "dividends")
    assert "dividends-symbol-core" in out
    assert "expected_params" in out
    assert "difficulty: L2" in out


def test_self_description_uses_row_key() -> None:
    contract = _dividends_contract()
    out = render_self_description(contract, "dividends")
    assert "symbol" in out
    assert "effective_date" in out


def test_sample_values_are_realistic() -> None:
    from scripts.generate_cap_fixtures import _sample_value

    assert _sample_value("symbol", {}) == "AAPL"
    assert _sample_value("currency", {}) == "USD"
    assert _sample_value("unknown_field", {}) == "<unknown_field>"
