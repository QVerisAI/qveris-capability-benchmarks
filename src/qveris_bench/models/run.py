from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from qveris_bench.models.base import EvidenceRef, FrozenModel, Sha256, StableId
from qveris_bench.models.enums import (
    CellState,
    FailureAttribution,
    OutcomeStatus,
    RunMode,
)


class RunCell(FrozenModel):
    run_key: str = Field(min_length=1)
    case_id: StableId
    provider_id: StableId
    access_path_id: StableId
    mode: RunMode
    round: int = Field(ge=1)
    applicable: bool = True
    applicability_reason: str | None = None
    state: CellState = CellState.PLANNED


class RunPlan(FrozenModel):
    suite_id: StableId
    suite_fingerprint: Sha256
    cells: tuple[RunCell, ...]


class ObservationEvent(FrozenModel):
    sequence: int = Field(ge=0)
    occurred_at: datetime
    event_type: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class TaskOutcome(FrozenModel):
    status: OutcomeStatus
    evidence_refs: tuple[EvidenceRef, ...] = ()
    unmet_conditions: tuple[str, ...] = ()
    failure_attribution: FailureAttribution | None = None
