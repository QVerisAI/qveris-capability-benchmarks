from __future__ import annotations

from pydantic import Field, model_validator

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)
from qveris_bench.models.enums import DimensionState, ReleaseFactType
from qveris_bench.models.metric import (
    UNSTRUCTURED_METRIC_PROPERTY_NAMES_SCHEMA,
    MetricDetails,
    MetricRanking,
    MetricScore,
    reject_unstructured_metric_keys,
)


class ReleaseFact(FrozenModel):
    fact_type: ReleaseFactType
    dimension_state: DimensionState | None = None
    dimension_id: StableId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
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
    def validate_metric_fields(self) -> ReleaseFact:
        reject_unstructured_metric_keys(self.details)
        if (self.metric_score is not None or self.metric_ranking is not None) and (
            self.dimension_state is not DimensionState.MEASURED
        ):
            raise ValueError("metric scores and rankings require a measured fact")
        metrics = tuple(
            metric
            for metric in (self.metric_score, self.metric_ranking)
            if metric is not None
        )
        if metrics and self.dimension_id is None:
            raise ValueError("metric scores and rankings require dimension_id")
        if any(metric.dimension_id != self.dimension_id for metric in metrics):
            raise ValueError("metric dimension_id must match the release fact")
        if any(
            not set(metric.evidence_refs).issubset(self.evidence_refs)
            for metric in metrics
        ):
            raise ValueError("metric evidence must be included in fact evidence_refs")
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
        if self.metric_score is not None and self.metric_ranking is not None:
            score_scope = (
                self.metric_score.cap_id,
                self.metric_score.provider_id,
                self.metric_score.access_path_id,
            )
            ranking_scope = (
                self.metric_ranking.cap_id,
                self.metric_ranking.provider_id,
                self.metric_ranking.access_path_id,
            )
            if score_scope != ranking_scope:
                raise ValueError(
                    "metric score and ranking must use the same CAP, Provider, "
                    "and Access Path"
                )
            score_method = (
                self.metric_score.cap_version,
                self.metric_score.method_digest,
                self.metric_score.suite_fingerprint,
                self.metric_score.scale_min,
                self.metric_score.scale_max,
                self.metric_score.unit,
                self.metric_score.direction,
            )
            ranking_method = (
                self.metric_ranking.cap_version,
                self.metric_ranking.method_digest,
                self.metric_ranking.suite_fingerprint,
                self.metric_ranking.scale_min,
                self.metric_ranking.scale_max,
                self.metric_ranking.unit,
                self.metric_ranking.direction,
            )
            if score_method != ranking_method:
                raise ValueError("metric score and ranking must use the same method")
        return self

    @model_validator(mode="after")
    def validate_dimension_state(self) -> ReleaseFact:
        if self.dimension_state == DimensionState.MEASURED and not self.evidence_refs:
            raise ValueError("measured dimension facts require evidence references")
        if self.dimension_state == DimensionState.DECLARED and self.evidence_refs:
            raise ValueError(
                "declared dimension facts cannot carry evidence references"
            )
        return self


class BenchmarkRelease(FrozenModel):
    release_id: StableId
    version: SemanticVersion
    suite_fingerprint: Sha256
    run_plan_digest: EvidenceRef
    evidence_ids: tuple[StableId, ...] = ()
    outcome_ids: tuple[StableId, ...] = ()
    developer_selection_facts: tuple[ReleaseFact, ...] = ()
    provider_feedback_facts: dict[StableId, tuple[ReleaseFact, ...]] = Field(
        default_factory=dict
    )
    limitations: tuple[str, ...] = ()
