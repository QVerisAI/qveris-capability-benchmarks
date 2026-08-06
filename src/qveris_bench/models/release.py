from __future__ import annotations

from typing import Any

from pydantic import Field

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)


class BenchmarkRelease(FrozenModel):
    release_id: StableId
    version: SemanticVersion
    suite_fingerprint: Sha256
    run_plan_digest: EvidenceRef
    evidence_ids: tuple[StableId, ...] = ()
    outcome_ids: tuple[StableId, ...] = ()
    developer_selection_facts: tuple[dict[str, Any], ...] = ()
    provider_feedback_facts: dict[StableId, tuple[dict[str, Any], ...]] = Field(
        default_factory=dict
    )
    limitations: tuple[str, ...] = ()
