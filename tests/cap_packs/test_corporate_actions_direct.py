from qveris_bench.cap_packs.corporate_actions.direct import (
    evaluate,
    evaluate_corporate_action_document,
    validate_public_outcome,
)
from qveris_bench.cap_packs.corporate_actions.models import (
    CorporateActionRequestIdentity,
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


def test_v2_positive_extraction_uses_frozen_request_identity_and_case_window() -> None:
    case = BenchmarkCase(
        case_id="hk-0700-split-market",
        cap_id="corporate-actions",
        question="test",
        input={
            "market": "HK",
            "symbol": "0700.HK",
            "start_date": "2014-01-01",
            "end_date": "2014-12-31",
        },
        expected_observations=("symbol", "identity_verified", "action_type", "date"),
        completion_conditions=("symbol", "identity_verified", "action_type", "date"),
        disclosure_limits=("sanitized_public",),
    )
    identity = CorporateActionRequestIdentity(
        market="HK",
        canonical_symbol="0700.HK",
        vendor_symbol="00700",
        parameter_path=("symbol",),
    )
    terminal = evaluate_corporate_action_document(
        "rongjuhui",
        {
            "status_code": 200,
            "data": {
                "data": [
                    {"exDate": "2013-05-15", "splitRatio": 2},
                    {"exDate": "2014-05-15", "splitRatio": 5},
                ]
            },
        },
        case,
        request_identity=identity,
    )

    assert terminal.state is CellState.COMPLETED
    assert terminal.facts == {
        "symbol": "0700.HK",
        "identity_verified": True,
        "identity_basis": "request_bound",
        "action_type": "split",
        "date": "2014-05-15",
        "ratio": 5.0,
    }


def test_v2_positive_extraction_rejects_wrong_response_identity() -> None:
    case = BenchmarkCase(
        case_id="us-aapl-split-market",
        cap_id="corporate-actions",
        question="test",
        input={
            "market": "US",
            "symbol": "AAPL",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        expected_observations=("symbol", "identity_verified", "action_type", "date"),
        completion_conditions=("symbol", "identity_verified", "action_type", "date"),
        disclosure_limits=("sanitized_public",),
    )
    terminal = evaluate_corporate_action_document(
        "twelve-data",
        {
            "status_code": 200,
            "data": {
                "meta": {"symbol": "MSFT"},
                "splits": [{"date": "2020-08-31", "ratio": 4}],
            },
        },
        case,
        request_identity=CorporateActionRequestIdentity(
            market="US",
            canonical_symbol="AAPL",
            vendor_symbol="AAPL",
            parameter_path=("symbol",),
        ),
    )

    assert terminal.state is CellState.PROVIDER_NEGATIVE
    assert "identity_verified" in terminal.unmet_conditions


def test_v2_positive_extraction_preserves_exchange_identity() -> None:
    case = BenchmarkCase(
        case_id="hk-0700-split-market",
        cap_id="corporate-actions",
        question="test",
        input={
            "market": "HK",
            "symbol": "0700.HK",
            "start_date": "2014-01-01",
            "end_date": "2014-12-31",
        },
        expected_observations=("symbol", "identity_verified", "action_type", "date"),
        completion_conditions=("symbol", "identity_verified", "action_type", "date"),
        disclosure_limits=("sanitized_public",),
    )
    identity = CorporateActionRequestIdentity(
        market="HK",
        canonical_symbol="0700.HK",
        vendor_symbol="0700:HKEX",
        parameter_path=("symbol",),
    )

    wrong_exchange = evaluate_corporate_action_document(
        "twelve-data",
        {
            "status_code": 200,
            "data": {
                "meta": {"symbol": "0700:SSE"},
                "splits": [{"date": "2014-05-15", "ratio": 5}],
            },
        },
        case,
        request_identity=identity,
    )
    exact_vendor = evaluate_corporate_action_document(
        "twelve-data",
        {
            "status_code": 200,
            "data": {
                "meta": {"symbol": "0700:HKEX"},
                "splits": [{"date": "2014-05-15", "ratio": 5}],
            },
        },
        case,
        request_identity=identity,
    )

    assert wrong_exchange.state is CellState.PROVIDER_NEGATIVE
    assert exact_vendor.state is CellState.COMPLETED


def test_v2_negative_control_does_not_treat_transport_failure_as_rejection() -> None:
    case = BenchmarkCase(
        case_id="invalid-corporate-actions-symbol-v2",
        cap_id="corporate-actions",
        question="test",
        input={"symbol": "NOTASTOCK"},
        negative_control=True,
        expected_observations=("validation_error",),
        completion_conditions=("validation_error",),
        disclosure_limits=("sanitized_public",),
    )

    rate_limited = evaluate_corporate_action_document(
        "eodhd", {"status_code": 429, "data": "rate limited"}, case
    )
    rejected = evaluate_corporate_action_document(
        "eodhd", {"status_code": 404, "data": "Symbol not found"}, case
    )

    assert rate_limited.state is CellState.INFRA_BLOCKED
    assert rate_limited.failure_attribution is FailureAttribution.RATE_LIMITED
    assert rejected.state is CellState.COMPLETED
    assert rejected.facts == {"validation_error": "provider_validation_error"}


def test_v2_infra_outcome_is_replayable_from_sanitized_public_facts() -> None:
    case = BenchmarkCase(
        case_id="invalid-corporate-actions-symbol-v2",
        cap_id="corporate-actions",
        question="test",
        input={"symbol": "NOTASTOCK"},
        negative_control=True,
        expected_observations=("validation_error",),
        completion_conditions=("validation_error",),
        disclosure_limits=("sanitized_public",),
    )
    binding = DirectBinding(
        binding_id="eodhd-invalid-corporate-actions-symbol-v2",
        suite_id="corporate-actions-v2",
        version="2.0.0",
        case_id=case.case_id,
        access_path_id="eodhd-corporate-actions-qveris",
        provider_id="eodhd",
        transport="qveris_connector",
        source_digest="sha256:" + "a" * 64,
        tool_id="tool",
        parameters={"symbol": "NOTASTOCK"},
        discovery_query="tool",
    )

    terminal = evaluate_corporate_action_document(
        "eodhd", {"status_code": 429, "data": "rate limited"}, case
    )
    replayed = validate_public_outcome(case, binding, terminal.facts)

    assert terminal.facts == {"execution_failure": "rate_limited"}
    assert replayed.state is CellState.INFRA_BLOCKED
    assert replayed.unmet_conditions == ("validation_error",)
    assert replayed.failure_attribution is FailureAttribution.RATE_LIMITED
