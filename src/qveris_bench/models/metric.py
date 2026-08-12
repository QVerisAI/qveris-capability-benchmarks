from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field, model_validator

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)

MetricDirection = Literal["higher_is_better", "lower_is_better"]
TieMethod = Literal["competition", "dense", "ordinal"]
type DetailScalar = str | int | float | bool | None
type DetailValue = DetailScalar | tuple[DetailScalar, ...]
type MetricDetails = dict[str, DetailValue]

UNSTRUCTURED_METRIC_PROPERTY_NAMES_SCHEMA: dict[str, Any] = {
    "not": {
        "anyOf": [
            {"pattern": "[sS][cC][oO][rR][eE]"},
            {"pattern": "[rR][aA][tT][iI][nN][gG]"},
            {"pattern": "[rR][aA][nN][kK]"},
        ]
    }
}


def reject_unstructured_metric_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(token in normalized for token in ("score", "rating", "ranking")):
                raise ValueError(
                    f"unstructured metric fields are forbidden: {key}; "
                    "aggregate and dimension metrics must use typed metric fields"
                )
            if normalized == "rank" or normalized.endswith("rank"):
                raise ValueError(
                    f"unstructured metric fields are forbidden: {key}; "
                    "aggregate and dimension metrics must use typed metric fields"
                )
            reject_unstructured_metric_keys(nested_value)
    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            reject_unstructured_metric_keys(nested_value)


class MetricScore(FrozenModel):
    metric_id: StableId
    dimension_id: StableId
    cap_id: StableId
    cap_version: SemanticVersion
    provider_id: StableId
    access_path_id: StableId
    method_version: SemanticVersion
    method_digest: EvidenceRef
    suite_fingerprint: Sha256
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    value: float = Field(allow_inf_nan=False)
    scale_min: float = Field(allow_inf_nan=False)
    scale_max: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1)
    direction: MetricDirection

    @model_validator(mode="after")
    def validate_scale(self) -> MetricScore:
        if self.scale_max <= self.scale_min:
            raise ValueError("scale_max must exceed scale_min")
        if not self.scale_min <= self.value <= self.scale_max:
            raise ValueError("metric score must be within the declared scale")
        return self


class MetricRanking(FrozenModel):
    metric_id: StableId
    dimension_id: StableId
    cap_id: StableId
    cap_version: SemanticVersion
    provider_id: StableId
    access_path_id: StableId
    method_version: SemanticVersion
    method_digest: EvidenceRef
    suite_fingerprint: Sha256
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    cohort_id: StableId
    cohort_digest: EvidenceRef
    rank: int = Field(ge=1)
    rank_of: int = Field(ge=1)
    tie_method: TieMethod
    direction: MetricDirection
    scale_min: float = Field(allow_inf_nan=False)
    scale_max: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rank(self) -> MetricRanking:
        if self.rank > self.rank_of:
            raise ValueError("rank cannot exceed rank_of")
        if self.scale_max <= self.scale_min:
            raise ValueError("scale_max must exceed scale_min")
        return self
