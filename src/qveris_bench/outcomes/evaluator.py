from __future__ import annotations

from typing import Any

from qveris_bench.models.enums import OutcomeStatus
from qveris_bench.models.run import TaskOutcome


def evaluate_outcome(
    completion_conditions: tuple[str, ...], facts: dict[str, Any], evidence_ref: str
) -> TaskOutcome:
    unmet = tuple(
        condition for condition in completion_conditions if condition not in facts
    )
    status = OutcomeStatus.COMPLETED if not unmet else OutcomeStatus.PARTIAL
    return TaskOutcome(
        status=status, evidence_refs=(evidence_ref,), unmet_conditions=unmet
    )
