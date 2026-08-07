from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import Field, model_validator

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import DimensionState
from qveris_bench.models.scenario import ScenarioRef


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


class ProfileDimension(FrozenModel):
    cap_id: StableId
    dimension: str = Field(min_length=1)
    dimension_state: DimensionState
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def reject_aggregate_fields(self) -> ProfileDimension:
        _reject_aggregate_keys(self.details)
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
