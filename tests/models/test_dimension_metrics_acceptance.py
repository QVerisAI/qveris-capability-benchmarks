from __future__ import annotations

import jsonschema
import pytest
from pydantic import ValidationError

from qveris_bench.models.enums import DimensionState, ReleaseFactType
from qveris_bench.models.profile import ProfileDimension
from qveris_bench.models.release import BenchmarkRelease, ReleaseFact

EVIDENCE_REF = "sha256:" + "a" * 64
METHOD_DIGEST = "sha256:" + "d" * 64
COHORT_DIGEST = "sha256:" + "e" * 64
SUITE_FINGERPRINT = "b" * 64


def _metric_score() -> dict[str, object]:
    return {
        "metric_id": "error-recoverability",
        "dimension_id": "agent-interface-error-recoverability",
        "cap_id": "stock-quote",
        "cap_version": "2.0.0",
        "provider_id": "finnhub",
        "access_path_id": "finnhub-qveris",
        "method_version": "1.0.0",
        "method_digest": METHOD_DIGEST,
        "suite_fingerprint": SUITE_FINGERPRINT,
        "evidence_refs": [EVIDENCE_REF],
        "value": 80,
        "scale_min": 0,
        "scale_max": 100,
        "unit": "points",
        "direction": "higher_is_better",
    }


def _metric_ranking() -> dict[str, object]:
    return {
        "metric_id": "error-recoverability",
        "dimension_id": "agent-interface-error-recoverability",
        "cap_id": "stock-quote",
        "cap_version": "2.0.0",
        "provider_id": "finnhub",
        "access_path_id": "finnhub-qveris",
        "method_version": "1.0.0",
        "method_digest": METHOD_DIGEST,
        "suite_fingerprint": SUITE_FINGERPRINT,
        "evidence_refs": [EVIDENCE_REF],
        "cohort_id": "stock-quote-v3-cohort",
        "cohort_digest": COHORT_DIGEST,
        "rank": 1,
        "rank_of": 4,
        "tie_method": "competition",
        "direction": "higher_is_better",
        "scale_min": 0,
        "scale_max": 100,
        "unit": "points",
    }


def test_ac1_release_fact_accepts_evidence_bound_dimension_score() -> None:
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        dimension_id="agent-interface-error-recoverability",
        details={"dimension": "agent-interface:error-recoverability"},
        metric_score=_metric_score(),
        evidence_refs=(EVIDENCE_REF,),
    )

    assert fact.metric_score is not None, "AC1 must retain the metric score"
    assert fact.metric_score.value == 80


def test_ac1_profile_dimension_accepts_evidence_bound_dimension_score() -> None:
    dimension = ProfileDimension(
        cap_id="stock-quote",
        dimension="agent-interface-error-recoverability",
        dimension_state=DimensionState.MEASURED,
        details={"agent_friendly": "subdimension observation"},
        metric_score=_metric_score(),
        evidence_refs=(EVIDENCE_REF,),
    )

    assert dimension.metric_score is not None, "AC1 profile score must validate"
    assert dimension.details["agent_friendly"] == "subdimension observation"


def test_ac4_legacy_facts_do_not_serialize_empty_metric_fields() -> None:
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        details={"dimension": "task-completion"},
    )
    dimension = ProfileDimension(
        cap_id="stock-quote",
        dimension="reliability",
        dimension_state=DimensionState.EVIDENCE_INSUFFICIENT,
    )

    assert "metric_score" not in fact.model_dump(), (
        "AC4 historical release bytes must not gain null metric fields"
    )
    assert "metric_ranking" not in fact.model_dump()
    assert "metric_score" not in dimension.model_dump()
    assert "metric_ranking" not in dimension.model_dump()


def test_ac2_release_fact_accepts_same_cohort_dimension_ranking() -> None:
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        dimension_id="agent-interface-error-recoverability",
        details={"dimension": "agent-interface:error-recoverability"},
        metric_score=_metric_score(),
        metric_ranking=_metric_ranking(),
        evidence_refs=(EVIDENCE_REF,),
    )

    assert fact.metric_ranking is not None, "AC2 must retain the ranking"
    assert fact.metric_ranking.rank == 1
    assert fact.metric_ranking.rank_of == 4


@pytest.mark.parametrize(
    "details",
    (
        {"provider_score": 99},
        {"provider_total_score": 99},
        {"cross_cap_ranking": 1},
        {"agent_friendly_rating": "A"},
    ),
)
def test_ac3_release_fact_rejects_unstructured_or_composite_scores(
    details: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="structured metric fields"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            details=details,
            evidence_refs=(EVIDENCE_REF,),
        )


def test_ac3_metric_score_and_ranking_require_measured_evidence() -> None:
    with pytest.raises(ValidationError, match="measured"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.DECLARED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score(),
        )

    with pytest.raises(ValidationError, match="evidence"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_ranking=_metric_ranking(),
        )


def test_ac3_ranking_rejects_invalid_bounds_and_mismatched_metric() -> None:
    invalid_ranking = _metric_ranking() | {"rank": 5, "rank_of": 4}
    with pytest.raises(ValidationError, match="rank cannot exceed rank_of"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_ranking=invalid_ranking,
            evidence_refs=(EVIDENCE_REF,),
        )

    with pytest.raises(ValidationError, match="same method_version"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score(),
            metric_ranking=_metric_ranking() | {"method_version": "2.0.0"},
            evidence_refs=(EVIDENCE_REF,),
        )

    with pytest.raises(ValidationError, match="same metric_id"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score(),
            metric_ranking=_metric_ranking() | {"metric_id": "parameter-clarity"},
            evidence_refs=(EVIDENCE_REF,),
        )


def test_ac3_score_and_ranking_require_the_same_cap_and_access_path() -> None:
    with pytest.raises(ValidationError, match="same CAP, Provider, and Access Path"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score(),
            metric_ranking=_metric_ranking() | {"access_path_id": "finnhub-native"},
            evidence_refs=(EVIDENCE_REF,),
        )

    with pytest.raises(ValidationError, match="profile CAP"):
        ProfileDimension(
            cap_id="sec-filing-evidence",
            dimension="agent-interface:error-recoverability",
            dimension_state=DimensionState.MEASURED,
            metric_score=_metric_score(),
            evidence_refs=(EVIDENCE_REF,),
        )


def test_ac3_metric_score_rejects_invalid_scale_and_out_of_range_value() -> None:
    with pytest.raises(ValidationError, match="scale_max must exceed scale_min"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score() | {"scale_min": 100, "scale_max": 100},
            evidence_refs=(EVIDENCE_REF,),
        )

    with pytest.raises(ValidationError, match="within the declared scale"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score() | {"value": 101},
            evidence_refs=(EVIDENCE_REF,),
        )


def test_ac1_exported_schema_accepts_typed_metric_and_rejects_ad_hoc_score() -> None:
    schema = BenchmarkRelease.model_json_schema(mode="validation")
    base_release = {
        "release_id": "stock-quote-2026-q3-v1",
        "version": "1.0.0",
        "suite_fingerprint": "b" * 64,
        "run_plan_digest": "sha256:" + "c" * 64,
    }
    valid = base_release | {
        "developer_selection_facts": [
            {
                "fact_type": "outcome",
                "dimension_state": "measured",
                "dimension_id": "agent-interface-error-recoverability",
                "details": {"dimension": "error-recoverability"},
                "metric_score": _metric_score(),
                "metric_ranking": _metric_ranking(),
                "evidence_refs": [EVIDENCE_REF],
            }
        ]
    }

    jsonschema.validate(valid, schema)

    invalid = base_release | {
        "developer_selection_facts": [
            {
                "fact_type": "outcome",
                "dimension_state": "measured",
                "details": {"provider_score": 99},
                "evidence_refs": [EVIDENCE_REF],
            }
        ]
    }
    with pytest.raises(jsonschema.ValidationError, match="provider_score"):
        jsonschema.validate(invalid, schema)


def test_ac3_metric_scope_and_evidence_must_match_parent_fact() -> None:
    with pytest.raises(ValidationError, match="dimension_id"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="parameter-clarity",
            metric_score=_metric_score(),
            evidence_refs=(EVIDENCE_REF,),
        )

    with pytest.raises(ValidationError, match="metric evidence"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            dimension_id="agent-interface-error-recoverability",
            metric_score=_metric_score() | {"evidence_refs": ["sha256:" + "f" * 64]},
            evidence_refs=(EVIDENCE_REF,),
        )


def test_ac3_exported_schema_rejects_nested_ad_hoc_scores() -> None:
    schema = BenchmarkRelease.model_json_schema(mode="validation")
    invalid = {
        "release_id": "stock-quote-2026-q3-v1",
        "version": "1.0.0",
        "suite_fingerprint": "b" * 64,
        "run_plan_digest": "sha256:" + "c" * 64,
        "developer_selection_facts": [
            {
                "fact_type": "outcome",
                "details": {"nested": {"provider_score": 99}},
            }
        ],
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)
