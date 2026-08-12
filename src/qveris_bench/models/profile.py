from __future__ import annotations

from pydantic import Field, model_validator

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import DimensionState
from qveris_bench.models.metric import (
    UNSTRUCTURED_METRIC_PROPERTY_NAMES_SCHEMA,
    MetricDetails,
    MetricRanking,
    MetricScore,
    reject_unstructured_metric_keys,
)
from qveris_bench.models.scenario import ScenarioRef


class ProfileDimension(FrozenModel):
    cap_id: StableId
    dimension: str = Field(min_length=1)
    dimension_state: DimensionState
    details: MetricDetails = Field(
        default_factory=dict,
        json_schema_extra={"propertyNames": UNSTRUCTURED_METRIC_PROPERTY_NAMES_SCHEMA},
    )
    metric_score: MetricScore | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    metric_ranking: MetricRanking | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_metric_fields(self) -> ProfileDimension:
        reject_unstructured_metric_keys(self.details)
        if (self.metric_score is not None or self.metric_ranking is not None) and (
            self.dimension_state is not DimensionState.MEASURED
        ):
            raise ValueError("metric scores and rankings require a measured dimension")
        if (
            self.metric_score is not None
            and self.metric_ranking is not None
            and self.metric_score.metric_id != self.metric_ranking.metric_id
        ):
            raise ValueError("metric score and ranking must use the same metric_id")
        if (
            self.metric_score is not None
            and self.metric_ranking is not None
            and self.metric_score.method_version != self.metric_ranking.method_version
        ):
            raise ValueError(
                "metric score and ranking must use the same method_version"
            )
        metrics = tuple(
            metric
            for metric in (self.metric_score, self.metric_ranking)
            if metric is not None
        )
        if any(metric.cap_id != self.cap_id for metric in metrics):
            raise ValueError("metric score and ranking must match the profile CAP")
        if any(metric.dimension_id != self.dimension for metric in metrics):
            raise ValueError("metric dimension_id must match the profile dimension")
        if any(
            not set(metric.evidence_refs).issubset(self.evidence_refs)
            for metric in metrics
        ):
            raise ValueError(
                "metric evidence must be included in dimension evidence_refs"
            )
        if len(metrics) == 2:
            score_scope = (metrics[0].provider_id, metrics[0].access_path_id)
            ranking_scope = (metrics[1].provider_id, metrics[1].access_path_id)
            if score_scope != ranking_scope:
                raise ValueError(
                    "metric score and ranking must use the same CAP, Provider, "
                    "and Access Path"
                )
            score_method = (
                metrics[0].cap_version,
                metrics[0].method_version,
                metrics[0].method_digest,
                metrics[0].suite_fingerprint,
                metrics[0].scale_min,
                metrics[0].scale_max,
                metrics[0].unit,
                metrics[0].direction,
            )
            ranking_method = (
                metrics[1].cap_version,
                metrics[1].method_version,
                metrics[1].method_digest,
                metrics[1].suite_fingerprint,
                metrics[1].scale_min,
                metrics[1].scale_max,
                metrics[1].unit,
                metrics[1].direction,
            )
            if score_method != ranking_method:
                raise ValueError("metric score and ranking must use the same method")
        return self

    @model_validator(mode="after")
    def validate_dimension_state(self) -> ProfileDimension:
        if self.dimension_state is DimensionState.MEASURED and not self.evidence_refs:
            raise ValueError("measured profile dimensions require evidence references")
        if (
            self.dimension_state is DimensionState.EVIDENCE_INSUFFICIENT
            and self.evidence_refs
        ):
            raise ValueError(
                "insufficient profile dimensions cannot carry evidence references"
            )
        return self


class TaskFitProfile(FrozenModel):
    profile_id: StableId
    version: SemanticVersion
    scenario_ref: ScenarioRef
    cap_dimensions: tuple[ProfileDimension, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
