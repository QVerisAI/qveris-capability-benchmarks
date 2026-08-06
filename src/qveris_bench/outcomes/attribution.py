from __future__ import annotations

from qveris_bench.models.enums import FailureAttribution


class AttributionError(ValueError):
    pass


def classify_failure(value: str) -> FailureAttribution:
    if value == "wrong_tool_selected":
        raise AttributionError(
            "wrong_tool_selected is not an approved failure attribution"
        )
    try:
        return FailureAttribution(value)
    except ValueError as exc:
        raise AttributionError(f"unapproved failure attribution: {value}") from exc
