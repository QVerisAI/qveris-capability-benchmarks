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


class RequestIdentity(FrozenModel):
    market: str = Field(pattern=r"^[A-Z]{2,8}$")
    canonical_symbol: str = Field(min_length=1)
    vendor_symbol: str = Field(min_length=1)


class RunCell(FrozenModel):
    run_key: str = Field(min_length=1)
    case_id: StableId
    case_input: dict[str, Any] = Field(default_factory=dict)
    provider_id: StableId
    access_path_id: StableId
    mode: RunMode
    round: int = Field(ge=1)
    applicable: bool = True
    applicability_reason: str | None = None
    state: CellState = CellState.PLANNED
    failure_attribution: FailureAttribution | None = None


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
