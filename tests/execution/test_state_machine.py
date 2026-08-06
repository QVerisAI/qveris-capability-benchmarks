import pytest

from qveris_bench.execution.state import StateTransitionError, transition
from qveris_bench.models.enums import CellState


def test_ac1_provider_negative_is_terminal() -> None:
    with pytest.raises(StateTransitionError, match="terminal"):
        transition(CellState.PROVIDER_NEGATIVE, CellState.RUNNING)


def test_ac1_infra_blocked_is_resumable() -> None:
    assert transition(CellState.INFRA_BLOCKED, CellState.RUNNING) is CellState.RUNNING


def test_ac1_excluded_requires_evidence() -> None:
    with pytest.raises(StateTransitionError, match="evidence"):
        transition(CellState.PLANNED, CellState.EXCLUDED)
    assert transition(CellState.PLANNED, CellState.EXCLUDED, "sha256:" + "a" * 64)
