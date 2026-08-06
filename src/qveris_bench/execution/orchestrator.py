from __future__ import annotations

from collections.abc import Awaitable, Callable

from qveris_bench.execution.resume import RunStateStore
from qveris_bench.execution.state import transition
from qveris_bench.models.enums import CellState
from qveris_bench.models.run import RunCell, RunPlan

CellExecutor = Callable[[RunCell], Awaitable[CellState]]


class RunOrchestrator:
    def __init__(self, state_store: RunStateStore, execute: CellExecutor) -> None:
        self._state_store = state_store
        self._execute = execute

    async def run(self, plan: RunPlan) -> dict[str, CellState]:
        states = self._state_store.read()
        for cell in plan.cells:
            current = states.get(cell.run_key, cell.state)
            if current not in {CellState.PLANNED, CellState.INFRA_BLOCKED}:
                continue
            states[cell.run_key] = transition(current, CellState.RUNNING)
            self._state_store.write(states)
            target = await self._execute(cell)
            states[cell.run_key] = transition(CellState.RUNNING, target)
            self._state_store.write(states)
        return states
