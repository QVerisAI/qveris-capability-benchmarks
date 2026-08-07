from __future__ import annotations

import pytest
from pydantic import ValidationError

from qveris_bench.models.enums import DimensionState, ReleaseFactType
from qveris_bench.models.release import ReleaseFact


def test_ac1_measured_fact_requires_evidence_references() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.MEASURED,
            details={},
        )
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        details={"environment_plan": "benchmark-e2e, three direct rounds"},
        evidence_refs=("sha256:" + "a" * 64,),
    )
    assert fact.dimension_state == DimensionState.MEASURED


def test_ac1_declared_fact_cannot_carry_evidence_references() -> None:
    with pytest.raises(ValidationError, match="declared"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.DECLARED,
            details={},
            evidence_refs=("sha256:" + "a" * 64,),
        )
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.DECLARED,
        details={},
    )
    assert fact.dimension_state == DimensionState.DECLARED


def test_ac1_insufficient_fact_carries_no_evidence_refs() -> None:
    fact = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.EVIDENCE_INSUFFICIENT,
        details={},
    )
    assert fact.dimension_state == DimensionState.EVIDENCE_INSUFFICIENT
    assert fact.evidence_refs == ()


def test_ac1_aggregate_keys_stay_forbidden() -> None:
    with pytest.raises(ValidationError, match="aggregate"):
        ReleaseFact(
            fact_type=ReleaseFactType.OUTCOME,
            dimension_state=DimensionState.DECLARED,
            details={"score": 1},
        )
