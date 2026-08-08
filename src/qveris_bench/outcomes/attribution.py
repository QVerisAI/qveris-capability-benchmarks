from __future__ import annotations

from qveris_bench.models.enums import FailureAttribution


class AttributionError(ValueError):
    pass


PROVIDER_SIDE_ATTRIBUTIONS = frozenset(
    {
        FailureAttribution.INVALID_PARAMETERS,
        FailureAttribution.PROVIDER_VALIDATION_ERROR,
        FailureAttribution.PROVIDER_RUNTIME_ERROR,
        FailureAttribution.AUTH_OR_ENTITLEMENT,
        FailureAttribution.RATE_LIMITED,
        FailureAttribution.NETWORK_OR_TIMEOUT,
        FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        FailureAttribution.TRUNCATED_OR_UNPAGED,
    }
)


def ensure_provider_side_attribution(
    attribution: FailureAttribution | None,
) -> FailureAttribution:
    if attribution is None:
        raise AttributionError("provider_negative requires a failure attribution")
    if attribution not in PROVIDER_SIDE_ATTRIBUTIONS:
        raise AttributionError(
            f"{attribution.value} is not a provider-side failure attribution"
        )
    return attribution


def classify_failure(value: str) -> FailureAttribution:
    if value == "wrong_tool_selected":
        raise AttributionError(
            "wrong_tool_selected is not an approved failure attribution"
        )
    try:
        return FailureAttribution(value)
    except ValueError as exc:
        raise AttributionError(f"unapproved failure attribution: {value}") from exc
