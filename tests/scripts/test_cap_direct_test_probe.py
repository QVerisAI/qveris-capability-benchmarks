"""Acceptance tests for the CAP Direct Test probe."""

from __future__ import annotations

from threading import Barrier

import pytest

from scripts.cap_direct_test_probe import (
    Case,
    SupplierProbe,
    build_executor,
    evaluate_cell,
    load_fixture,
    probe_state,
    run_probe,
)


def test_executor_reuses_one_discovery_for_repeated_frozen_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []

    class Response:
        def __init__(self, body: dict) -> None:
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            import json

            return json.dumps(self.body).encode("utf-8")

    def urlopen(request, timeout):
        requests.append((request.full_url, timeout))
        if request.full_url.endswith("/search"):
            return Response({"search_id": "frozen-search"})
        return Response(
            {
                "result": {"status_code": 200, "data": {"Date": "2020-08-31"}},
                "billing": {"list_amount_credits": 1},
                "elapsed_time_ms": 100,
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    execute = build_executor("https://qveris.ai/api/v1", "test-key")

    execute("provider.splits", {"symbol": "AAPL"})
    execute("provider.splits", {"symbol": "NOTASTOCK"})

    assert sum(url.endswith("/search") for url, _ in requests) == 1
    assert len(requests) == 3


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
    assert probe_state(results) == "n_a"


def test_ac5_search_timeout_is_a_terminal_unavailable_observation() -> None:
    def execute(tool_id, parameters):
        raise TimeoutError("gateway search timed out")

    probe = SupplierProbe(
        supplier="EODHD",
        provider_id="eodhd",
        access_path_id="eodhd-corporate-actions-qveris",
        tool_id="eodhd.splits",
        cases=(_case(),),
    )

    results = run_probe((probe,), execute, rounds=1)

    assert results[0].state == "n_a"
    assert "timed out" in results[0].notes


def test_direct_test_runs_independent_provider_paths_concurrently() -> None:
    barrier = Barrier(2)

    def execute(_tool_id, _parameters):
        barrier.wait(timeout=1)
        return {
            "status_code": 200,
            "data": {"Date": "2020-08-31", "Stock Splits": "4:1"},
        }

    probes = tuple(
        SupplierProbe(
            supplier=supplier,
            provider_id=provider_id,
            access_path_id=f"{provider_id}-corporate-actions-qveris",
            tool_id=f"{provider_id}.splits",
            cases=(_case(),),
        )
        for supplier, provider_id in (("Alpha", "alpha"), ("Beta", "beta"))
    )

    results = run_probe(probes, execute, rounds=1)

    assert [result.provider_id for result in results] == ["alpha", "beta"]
    assert all(result.state == "passed" for result in results)


def test_ac5_any_failed_or_unavailable_cell_fails_the_probe() -> None:
    assert (
        probe_state(
            [
                evaluate_cell(_case(), {"status_code": 200, "data": {"Date": "x"}}),
                evaluate_cell(
                    _case(),
                    {
                        "status_code": 200,
                        "data": {"Date": "x", "Stock Splits": "2:1"},
                    },
                ),
            ]
        )
        == "failed"
    )


def test_fixture_loads() -> None:
    from pathlib import Path

    probes = load_fixture(
        Path("scripts/fixtures/cap-direct-test-corporate-actions.yaml"),
        Path("providers"),
    )
    assert {probe.supplier for probe in probes} == {
        "EODHD",
        "Twelve Data",
        "Alpha Vantage",
        "Massive",
    }
    assert all(probe.access_path_id for probe in probes)


def test_all_direct_fixtures_bind_registered_access_paths() -> None:
    from pathlib import Path

    for fixture in sorted(Path("scripts/fixtures").glob("cap-direct-test-*.yaml")):
        probes = load_fixture(fixture, Path("providers"))
        assert probes


def test_legacy_direct_cohort_exclusions_remain_explicit() -> None:
    from pathlib import Path

    import yaml

    # corporate-actions retains legacy exclusions; dividends migrated all
    # suppliers into the formal cohort with registered access paths.
    expected = {
        "cap-direct-test-corporate-actions.yaml": (4, 1),
        "cap-direct-test-dividends.yaml": (6, 0),
    }
    for name, (suppliers, excluded) in expected.items():
        document = yaml.safe_load((Path("scripts/fixtures") / name).read_text())
        assert len(document["suppliers"]) == suppliers
        assert len(document.get("excluded_legacy_suppliers", [])) == excluded
