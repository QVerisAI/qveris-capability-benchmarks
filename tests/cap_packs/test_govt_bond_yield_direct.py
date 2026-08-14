import math

import pytest

from qveris_bench.cap_packs.govt_bond_yield.direct import (
    evaluate_government_bond_document,
    validate_public_outcome,
)
from qveris_bench.cap_packs.govt_bond_yield.models import (
    GovernmentBondRequestIdentity,
)
from qveris_bench.execution.direct_binding import DirectBinding
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.suite import BenchmarkCase


def _case(*, negative: bool = False) -> BenchmarkCase:
    return BenchmarkCase(
        case_id="unsupported-country-10y" if negative else "us-10y-baseline",
        cap_id="govt-bond-yield",
        question="test",
        input={
            "country": "ZZ" if negative else "US",
            "tenor": "10Y",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
        negative_control=negative,
        expected_observations=("validation_error",)
        if negative
        else ("symbol", "date", "close", "identity_verified"),
        completion_conditions=("validation_error",)
        if negative
        else ("symbol", "date", "close", "identity_verified"),
        disclosure_limits=("sanitized_public",),
    )


def _identity(provider_id: str = "stlouisfed-fred") -> GovernmentBondRequestIdentity:
    return GovernmentBondRequestIdentity(
        country="US",
        tenor="10Y",
        vendor_identifier="DGS10" if provider_id == "stlouisfed-fred" else "US",
        parameter_path=("series_id",)
        if provider_id == "stlouisfed-fred"
        else ("country",),
        response_aliases=("DGS10", "UST10Y", "US10Y"),
    )


def test_fred_uses_latest_finite_observation_in_fixed_window() -> None:
    result = evaluate_government_bond_document(
        "stlouisfed-fred",
        {
            "status_code": 200,
            "data": {
                "seriess": [{"id": "DGS10", "units": "Percent"}],
                "observations": [
                    {"date": "2025-01-02", "value": "4.50"},
                    {"date": "2024-12-30", "value": "."},
                    {"date": "2024-12-31", "value": "4.38"},
                    {"date": "2024-01-02", "value": "3.95"},
                ],
            },
        },
        _case(),
        request_identity=_identity(),
    )

    assert result.state is CellState.COMPLETED
    assert result.facts == {
        "symbol": "DGS10",
        "date": "2024-12-31",
        "close": 4.38,
        "identity_verified": True,
        "identity_basis": "request_bound",
        "unit": "Percent",
        "source": "FRED",
    }


@pytest.mark.parametrize("value", [0, -0.25])
def test_qveris_finance_accepts_finite_zero_or_negative_yields(value: float) -> None:
    result = evaluate_government_bond_document(
        "qveris-finance",
        {
            "status_code": 200,
            "data": {
                "data": [
                    {
                        "symbol": "US10Y",
                        "date": "2024-12-31",
                        "close": value,
                        "unit": "%",
                        "source": "QVeris Finance",
                    }
                ]
            },
        },
        _case(),
        request_identity=_identity("qveris-finance"),
    )

    assert result.state is CellState.COMPLETED
    assert result.facts["close"] == value
    assert result.facts["identity_basis"] == "response_field"


@pytest.mark.parametrize("value", [math.nan, math.inf, "not-a-number"])
def test_non_finite_or_non_numeric_yields_do_not_pass(value: object) -> None:
    result = evaluate_government_bond_document(
        "qveris-finance",
        {
            "status_code": 200,
            "data": {
                "data": [{"symbol": "US10Y", "date": "2024-12-31", "close": value}]
            },
        },
        _case(),
        request_identity=_identity("qveris-finance"),
    )
    assert result.state is CellState.PROVIDER_NEGATIVE


def test_wrong_returned_benchmark_identity_does_not_pass() -> None:
    result = evaluate_government_bond_document(
        "qveris-finance",
        {
            "status_code": 200,
            "data": {
                "data": [{"symbol": "CN10Y", "date": "2024-12-31", "close": 1.68}]
            },
        },
        _case(),
        request_identity=_identity("qveris-finance"),
    )
    assert result.state is CellState.PROVIDER_NEGATIVE
    assert "identity_verified" in result.unmet_conditions


@pytest.mark.parametrize(
    ("status_code", "attribution"),
    [
        (401, FailureAttribution.AUTH_OR_ENTITLEMENT),
        (403, FailureAttribution.AUTH_OR_ENTITLEMENT),
        (429, FailureAttribution.RATE_LIMITED),
        (503, FailureAttribution.PROVIDER_RUNTIME_ERROR),
    ],
)
def test_transport_failures_never_complete_the_negative_control(
    status_code: int, attribution: FailureAttribution
) -> None:
    result = evaluate_government_bond_document(
        "stlouisfed-fred",
        {"status_code": status_code, "data": {"error_message": "failed"}},
        _case(negative=True),
        request_identity=GovernmentBondRequestIdentity(
            country="ZZ",
            tenor="10Y",
            vendor_identifier="QVERIS_UNSUPPORTED_ZZ_10Y",
            parameter_path=("series_id",),
            response_aliases=(),
        ),
    )
    assert result.state is CellState.INFRA_BLOCKED
    assert result.failure_attribution is attribution


def test_explicit_provider_rejection_completes_negative_control() -> None:
    result = evaluate_government_bond_document(
        "stlouisfed-fred",
        {
            "status_code": 400,
            "data": {"error_message": "Bad Request. The series does not exist."},
        },
        _case(negative=True),
        request_identity=GovernmentBondRequestIdentity(
            country="ZZ",
            tenor="10Y",
            vendor_identifier="QVERIS_UNSUPPORTED_ZZ_10Y",
            parameter_path=("series_id",),
            response_aliases=(),
        ),
    )
    assert result.state is CellState.COMPLETED
    assert result.facts == {"validation_error": "provider_validation_error"}


def test_public_replay_reconstructs_exact_positive_outcome() -> None:
    case = _case()
    binding = DirectBinding(
        binding_id="fred-us-10y-baseline",
        suite_id="govt-bond-yield-v1",
        version="1.0.0",
        case_id=case.case_id,
        access_path_id="stlouisfed-fred-govt-bond-yield-qveris",
        provider_id="stlouisfed-fred",
        transport="qveris_connector",
        source_digest="sha256:" + "a" * 64,
        tool_id="fred",
        parameters={"series_id": "DGS10"},
        discovery_query="fred",
        request_identity=_identity().model_dump(mode="json"),
    )
    facts = {
        "symbol": "DGS10",
        "date": "2024-12-31",
        "close": 4.38,
        "identity_verified": True,
        "identity_basis": "request_bound",
        "unit": "Percent",
        "source": "FRED",
    }
    outcome = validate_public_outcome(case, binding, facts)
    assert outcome.state is CellState.COMPLETED
    assert outcome.unmet_conditions == ()
