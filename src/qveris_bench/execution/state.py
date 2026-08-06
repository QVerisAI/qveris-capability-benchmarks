from __future__ import annotations

from qveris_bench.models.enums import CellState


class StateTransitionError(ValueError):
    pass


_TERMINAL = {
    CellState.COMPLETED,
    CellState.PROVIDER_NEGATIVE,
    CellState.EXCLUDED,
    CellState.NOT_APPLICABLE,
}


def transition(
    current: CellState, target: CellState, evidence_digest: str | None = None
) -> CellState:
    if current in _TERMINAL and current is not target:
        raise StateTransitionError(f"{current.value} is terminal")
    if target is CellState.EXCLUDED and evidence_digest is None:
        raise StateTransitionError("excluded requires evidence")
    return target
