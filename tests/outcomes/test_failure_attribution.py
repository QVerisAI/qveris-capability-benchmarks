import pytest

from qveris_bench.models.enums import FailureAttribution
from qveris_bench.outcomes.attribution import AttributionError, classify_failure


def test_ac3_failure_attribution_uses_approved_taxonomy() -> None:
    assert classify_failure("rate_limited") is FailureAttribution.RATE_LIMITED
    assert classify_failure("unknown") is FailureAttribution.UNKNOWN


def test_ac3_wrong_tool_selected_is_rejected() -> None:
    with pytest.raises(AttributionError, match="wrong_tool_selected"):
        classify_failure("wrong_tool_selected")
