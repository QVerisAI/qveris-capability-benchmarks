import pytest

from qveris_bench.models.enums import FailureAttribution
from qveris_bench.outcomes.attribution import (
    AttributionError,
    classify_failure,
    classify_provider_negative_reason,
)


def test_ac3_failure_attribution_uses_approved_taxonomy() -> None:
    assert classify_failure("rate_limited") is FailureAttribution.RATE_LIMITED
    assert classify_failure("unknown") is FailureAttribution.UNKNOWN


def test_ac3_wrong_tool_selected_is_rejected() -> None:
    with pytest.raises(AttributionError, match="wrong_tool_selected"):
        classify_failure("wrong_tool_selected")


def test_ac4_provider_side_reasons_map_to_approved_attributions() -> None:
    assert (
        classify_provider_negative_reason("fiscal_year_unavailable")
        is FailureAttribution.EMPTY_OR_PARTIAL_DATA
    )
    assert (
        classify_provider_negative_reason("filing_type_not_supported")
        is FailureAttribution.PROVIDER_VALIDATION_ERROR
    )


def test_ac4_benchmark_side_reasons_are_not_publishable() -> None:
    assert classify_provider_negative_reason("invalid_revenue") is None
    assert classify_provider_negative_reason("unexpected_response_shape") is None
    assert classify_provider_negative_reason("invalid_timestamp") is None
