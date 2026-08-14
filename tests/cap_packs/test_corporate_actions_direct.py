from qveris_bench.cap_packs.corporate_actions.direct import (
    evaluate,
    validate_public_outcome,
)
from qveris_bench.execution.direct_binding import DirectBinding
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.suite import BenchmarkCase


def test_positive_responses_extract_only_the_cap_contract() -> None:
    payloads = {
        "eodhd": {"status_code": 200, "data": 'Date,"Stock Splits"\n2020-08-31,4/1\n'},
        "twelve-data": {
            "status_code": 200,
            "data": {"meta": {"symbol": "AAPL"}, "splits": [{"date": "2020-08-31"}]},
        },
        "alpha-vantage": {
            "status_code": 200,
            "data": {"symbol": "AAPL", "data": [{"effective_date": "2020-08-31"}]},
        },
        "massive-stocks": {
            "status_code": 200,
            "data": {"results": [{"ticker": "AAPL", "execution_date": "2020-08-31"}]},
        },
    }
    for provider_id, payload in payloads.items():
        terminal = evaluate(provider_id, "aapl-splits-fixed-window", payload)
        assert terminal.state is CellState.COMPLETED
        assert terminal.facts == {
            "symbol": "AAPL",
            "action_type": "split",
            "date": "2020-08-31",
        }


def test_only_explicit_negative_responses_complete_the_control() -> None:
    eodhd = evaluate(
        "eodhd",
        "invalid-corporate-actions-symbol",
        {"status_code": 404, "data": "Symbol not found"},
    )
    twelve = evaluate(
        "twelve-data",
        "invalid-corporate-actions-symbol",
        {
            "status_code": 4042,
            "data": {"status": "error", "message": "symbol is invalid"},
        },
    )
    alpha = evaluate(
        "alpha-vantage",
        "invalid-corporate-actions-symbol",
        {"status_code": 200, "data": {"symbol": "NOTASTOCK", "data": []}},
    )
    assert eodhd.state is twelve.state is CellState.COMPLETED
    assert eodhd.attribution is FailureAttribution.PROVIDER_VALIDATION_ERROR
    assert alpha.state is CellState.PROVIDER_NEGATIVE


def test_public_positive_outcome_requires_an_iso_date_in_the_case_window() -> None:
    case = BenchmarkCase(
        case_id="aapl-splits-fixed-window",
        cap_id="corporate-actions",
        question="test",
        input={"symbol": "AAPL", "start_date": "2020-01-01", "end_date": "2026-08-13"},
        expected_observations=("symbol", "action_type", "date"),
        completion_conditions=("test",),
        disclosure_limits=("sanitized_public",),
        applicable_provider_ids=("eodhd",),
    )
    binding = DirectBinding(
        binding_id="eodhd-aapl-splits",
        suite_id="corporate-actions-v1",
        version="1.0.0",
        case_id=case.case_id,
        access_path_id="eodhd-corporate-actions-qveris",
        provider_id="eodhd",
        transport="qveris_connector",
        source_digest="sha256:" + "a" * 64,
        tool_id="tool",
        parameters={},
        discovery_query="tool",
    )
    for value in ("abcdefghij", "2014-01-01"):
        outcome = validate_public_outcome(
            case,
            binding,
            {"symbol": "AAPL", "action_type": "split", "date": value},
        )
        assert outcome.state is CellState.INFRA_BLOCKED
