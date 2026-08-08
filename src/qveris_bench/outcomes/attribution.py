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


_REASON_ATTRIBUTIONS = {
    "unavailable_quote": FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    "fiscal_year_unavailable": FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    "filing_unavailable": FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    "evidence_passage_missing": FailureAttribution.EMPTY_OR_PARTIAL_DATA,
    "filing_type_not_supported": FailureAttribution.PROVIDER_VALIDATION_ERROR,
    "invalid_parameters": FailureAttribution.INVALID_PARAMETERS,
    "provider_validation_error": FailureAttribution.PROVIDER_VALIDATION_ERROR,
    "provider_runtime_error": FailureAttribution.PROVIDER_RUNTIME_ERROR,
    "auth_or_entitlement": FailureAttribution.AUTH_OR_ENTITLEMENT,
    "rate_limited": FailureAttribution.RATE_LIMITED,
    "network_or_timeout": FailureAttribution.NETWORK_OR_TIMEOUT,
    "truncated_or_unpaged": FailureAttribution.TRUNCATED_OR_UNPAGED,
}


def classify_provider_negative_reason(reason: str) -> FailureAttribution | None:
    """只承认供应商侧 reason；基准侧解析失败返回 None，禁止发布为 provider_negative."""
    return _REASON_ATTRIBUTIONS.get(reason)


def classify_failure(value: str) -> FailureAttribution:
    if value == "wrong_tool_selected":
        raise AttributionError(
            "wrong_tool_selected is not an approved failure attribution"
        )
    try:
        return FailureAttribution(value)
    except ValueError as exc:
        raise AttributionError(f"unapproved failure attribution: {value}") from exc
