from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from qveris_bench.execution.resume import RunStateStore
from qveris_bench.execution.retry import retry_with_budget
from qveris_bench.execution.state import transition
from qveris_bench.models.enums import CellState
from qveris_bench.models.run import RunCell, RunPlan


@dataclass(frozen=True)
class CellExecutionResult:
    state: CellState
    evidence_digest: str | None = None


CellExecutor = Callable[[RunCell], Awaitable[CellExecutionResult]]


class RunOrchestrator:
    def __init__(
        self, state_store: RunStateStore, execute: CellExecutor, retry_attempts: int = 1
    ) -> None:
        self._state_store = state_store
        self._execute = execute
        self._retry_attempts = retry_attempts

    async def run(self, plan: RunPlan) -> dict[str, CellState]:
        states = self._state_store.read(plan.suite_fingerprint)
        for cell in plan.cells:
            current = states.get(cell.run_key, cell.state)
            if current not in {CellState.PLANNED, CellState.INFRA_BLOCKED}:
                continue
            states[cell.run_key] = transition(current, CellState.RUNNING)
            self._state_store.write(plan.suite_fingerprint, states)
            try:

                async def execute_cell(cell: RunCell = cell) -> CellExecutionResult:
                    return await self._execute(cell)

                result = await retry_with_budget(execute_cell, self._retry_attempts)
                states[cell.run_key] = transition(
                    CellState.RUNNING, result.state, result.evidence_digest
                )
            except Exception:
                states[cell.run_key] = CellState.INFRA_BLOCKED
                self._state_store.write(plan.suite_fingerprint, states)
                raise
            self._state_store.write(plan.suite_fingerprint, states)
        return states
