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


def test_comparison_fields_never_contain_angle_placeholders() -> None:
    """A <field> placeholder in a comparison field would deterministically fail."""
    from scripts.generate_cap_fixtures import (
        render_direct_test,
        render_interpretation,
        render_param_fill,
        render_recovery,
    )

    contract = _dividends_contract()
    for render in (
        render_param_fill,
        render_direct_test,
        render_interpretation,
        render_recovery,
    ):
        out = render(contract, "dividends")
        # comparison values must be <TODO> markers, not fabricated <field> names
        assert "<symbol>" not in out, f"{render.__name__} fabricated a fake value"


def test_missing_contract_section_fails_closed() -> None:

    from scripts.generate_cap_fixtures import _validate_contract

    contract = _dividends_contract()
    assert _validate_contract(contract) == []
    broken = dict(contract)
    broken.pop("field_spec")
    assert "field_spec" in _validate_contract(broken)


def test_generated_yaml_is_parseable() -> None:
    import yaml

    from scripts.generate_cap_fixtures import (
        render_direct_test,
        render_interpretation,
        render_param_fill,
        render_recovery,
        render_self_description,
    )

    contract = _dividends_contract()
    for render in (
        render_direct_test,
        render_param_fill,
        render_interpretation,
        render_recovery,
        render_self_description,
    ):
        content = render(contract, "dividends")
        yaml.safe_load(content)  # must not raise
