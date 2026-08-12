from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, WithJsonSchema, model_validator

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)

MetricDirection = Literal["higher_is_better", "lower_is_better"]
TieMethod = Literal["competition", "dense", "ordinal"]
UNSTRUCTURED_METRIC_PROPERTY_NAMES_SCHEMA: dict[str, Any] = {
    "not": {
        "anyOf": [
            {"pattern": "[sS][cC][oO][rR][eE]"},
            {"pattern": "[rR][aA][tT][iI][nN][gG]"},
            {"pattern": "[rR][aA][nN][kK]"},
        ]
    }
}


def _validate_detail_key(value: Any) -> str:
    reject_unstructured_metric_keys({str(value): None})
    return str(value)


type MetricDetailKey = Annotated[
    str,
    BeforeValidator(_validate_detail_key),
    WithJsonSchema(
        {"type": "string", **UNSTRUCTURED_METRIC_PROPERTY_NAMES_SCHEMA},
        mode="validation",
    ),
]
type DetailScalar = str | int | float | bool | None
type DetailValue = (
    DetailScalar | tuple["DetailValue", ...] | dict[MetricDetailKey, "DetailValue"]
)
type MetricDetails = dict[MetricDetailKey, DetailValue]


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


class MetricDefinition(FrozenModel):
    definition_id: StableId
    cap_id: StableId
    cap_version: SemanticVersion
    metric_id: StableId
    dimension_id: StableId
    method_version: SemanticVersion
    method_digest: EvidenceRef
    scale_min: float = Field(allow_inf_nan=False)
    scale_max: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1)
    direction: MetricDirection

    @model_validator(mode="after")
    def validate_scale(self) -> MetricDefinition:
        if self.scale_max <= self.scale_min:
            raise ValueError("scale_max must exceed scale_min")
        return self


def metric_definition_digest(definition: MetricDefinition) -> str:
    return sha256_digest(_canonical_json_bytes(definition.model_dump(mode="json")))


class MetricScore(FrozenModel):
    metric_id: StableId
    definition_digest: EvidenceRef
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
    definition_digest: EvidenceRef
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


def metric_ranking_cohort_digest(rankings: list[MetricRanking]) -> str:
    first = rankings[0]
    payload = {
        "cohort_id": first.cohort_id,
        "metric_id": first.metric_id,
        "definition_digest": first.definition_digest,
        "dimension_id": first.dimension_id,
        "cap_id": first.cap_id,
        "cap_version": first.cap_version,
        "method_version": first.method_version,
        "method_digest": first.method_digest,
        "suite_fingerprint": first.suite_fingerprint,
        "rank_of": first.rank_of,
        "tie_method": first.tie_method,
        "direction": first.direction,
        "scale_min": first.scale_min,
        "scale_max": first.scale_max,
        "unit": first.unit,
        "members": sorted(
            (ranking.provider_id, ranking.access_path_id) for ranking in rankings
        ),
    }
    return sha256_digest(_canonical_json_bytes(payload))


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()
