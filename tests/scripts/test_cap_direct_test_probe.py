"""Acceptance tests for the CAP Direct Test probe."""

from __future__ import annotations

from scripts.cap_direct_test_probe import (
    Case,
    SupplierProbe,
    evaluate_cell,
    load_fixture,
    run_probe,
)


def _case(**kwargs) -> Case:
    defaults = {
        "case_id": "aapl-splits",
        "parameters": {"symbol": "AAPL"},
        "expected_observations": ("Stock Splits", "Date"),
        "negative_control": False,
    }
    defaults.update(kwargs)
    return Case(**defaults)


def test_ac1_positive_all_observations_present_passes() -> None:
    outcome = {
        "status_code": 200,
        "data": {"Date": "2020-08-31", "Stock Splits": "4:1"},
    }
    result = evaluate_cell(_case(), outcome)
    assert result.state == "passed"


def test_ac2_positive_missing_observation_fails() -> None:
    outcome = {"status_code": 200, "data": {"Date": "2020-08-31"}}
    result = evaluate_cell(_case(), outcome)
    assert result.state == "failed"
    assert result.missing == ("Stock Splits",)


def test_ac3_negative_control_with_fabricated_data_fails() -> None:
    outcome = {
        "status_code": 200,
        "data": {"results": [{"symbol": "NOTASTOCK", "date": "2026-01-01"}]},
    }
    result = evaluate_cell(
        _case(negative_control=True, expected_observations=()), outcome
    )
    assert result.state == "failed"


def test_ac4_negative_control_empty_response_passes() -> None:
    outcome = {"status_code": 200, "data": {}}
    result = evaluate_cell(
        _case(negative_control=True, expected_observations=()), outcome
    )
    assert result.state == "passed"


def test_ac6_csv_string_response_observations_match_header() -> None:
    outcome = {
        "status_code": 200,
        "data": 'Date,"Stock Splits"\n2020-08-31,4.000000/1.000000\n',
    }
    result = evaluate_cell(_case(), outcome)
    assert result.state == "passed"


def test_ac7_negative_control_empty_event_list_passes() -> None:
    outcome = {"status_code": 200, "data": {"symbol": "NOTASTOCK", "data": []}}
    result = evaluate_cell(
        _case(negative_control=True, expected_observations=()), outcome
    )
    assert result.state == "passed"


def test_ac8_negative_control_nested_error_envelope_passes() -> None:
    outcome = {
        "status_code": 200,
        "data": {
            "success": True,
            "data": {
                "msg": "For input string: ZZZZZZZZ",
                "code": "500",
                "data": {},
            },
            "message": "操作成功",
        },
    }
    result = evaluate_cell(
        _case(negative_control=True, expected_observations=()), outcome
    )
    assert result.state == "passed"


def test_ac5_execution_unauthorized_is_n_a() -> None:
    def execute(tool_id, parameters):
        raise RuntimeError("execute HTTP 401")

    probe = SupplierProbe(
        supplier="EODHD",
        provider_id="eodhd",
        access_path_id="eodhd-corporate-actions-qveris",
        tool_id="eodhd.splits",
        cases=(_case(),),
    )
    results = run_probe((probe,), execute, rounds=1)
    assert results[0].state == "n_a"


def test_fixture_loads() -> None:
    from pathlib import Path

    probes = load_fixture(
        Path("scripts/fixtures/cap-direct-test-corporate-actions.yaml")
    )
    assert {probe.supplier for probe in probes} == {
        "EODHD",
        "Twelve Data",
        "Alpha Vantage",
        "Massive",
        "恒生聚源",
    }
    assert all(probe.access_path_id for probe in probes)
