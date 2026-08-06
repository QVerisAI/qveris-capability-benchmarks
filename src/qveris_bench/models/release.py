from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import Field, model_validator

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    Sha256,
    StableId,
)
from qveris_bench.models.enums import ReleaseFactType


def _reject_aggregate_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(
                token in normalized for token in ("score", "rating", "agentfriendly")
            ):
                raise ValueError(f"aggregate field is forbidden: {key}")
            _reject_aggregate_keys(nested_value)
    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            _reject_aggregate_keys(nested_value)


class ReleaseFact(FrozenModel):
    fact_type: ReleaseFactType
    details: dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra={
            "propertyNames": {
                "not": {
                    "anyOf": [
                        {"pattern": "[s][c][o][r][e]"},
                        {"pattern": "[r][a][t][i][n][g]"},
                        {"pattern": "[a][g][e][n][t][f][r][i][e][n][d][l][y]"},
                    ]
                }
            },
        },
    )
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def reject_aggregate_fields(self) -> ReleaseFact:
        _reject_aggregate_keys({"fact_type": self.fact_type})
        _reject_aggregate_keys(self.details)
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
