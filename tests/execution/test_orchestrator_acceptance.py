import asyncio
from pathlib import Path

from qveris_bench.execution.orchestrator import CellExecutionResult, RunOrchestrator
from qveris_bench.execution.resume import RunStateStore
from qveris_bench.models.enums import CellState
from qveris_bench.models.run import RunCell, RunPlan


def test_ac3_orchestrator_executes_planned_cells_in_order(tmp_path: Path) -> None:
    async def run() -> None:
        observed: list[str] = []

        async def execute(cell: RunCell) -> CellExecutionResult:
            observed.append(cell.run_key)
            return CellExecutionResult(CellState.COMPLETED)

        plan = RunPlan(
            suite_id="suite-1",
            suite_fingerprint="a" * 64,
            cells=(
                RunCell(
                    run_key="one",
                    case_id="case-1",
                    provider_id="p-1",
                    access_path_id="a-1",
                    mode="direct",
                    round=1,
                ),
                RunCell(
                    run_key="two",
                    case_id="case-1",
                    provider_id="p-1",
                    access_path_id="a-1",
                    mode="direct",
                    round=2,
                ),
            ),
        )
        orchestrator = RunOrchestrator(RunStateStore(tmp_path / "state.json"), execute)
        states = await orchestrator.run(plan)
        assert observed == ["one", "two"]
        assert states["two"] is CellState.COMPLETED

    asyncio.run(run())


def test_ac3_executor_error_is_resumable(tmp_path: Path) -> None:
    async def run() -> None:
        async def execute(_: RunCell) -> CellExecutionResult:
            raise RuntimeError("network lost")

        plan = RunPlan(
            suite_id="suite-1",
            suite_fingerprint="a" * 64,
            cells=(
                RunCell(
                    run_key="one",
                    case_id="case-1",
                    provider_id="p-1",
                    access_path_id="a-1",
                    mode="direct",
                    round=1,
                ),
            ),
        )
        orchestrator = RunOrchestrator(RunStateStore(tmp_path / "state.json"), execute)
        try:
            await orchestrator.run(plan)
        except RuntimeError:
            pass
        states = RunStateStore(tmp_path / "state.json").read(plan.suite_fingerprint)
        assert states["one"] is CellState.INFRA_BLOCKED

    asyncio.run(run())
