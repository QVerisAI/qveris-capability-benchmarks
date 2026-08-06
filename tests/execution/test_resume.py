import asyncio
from pathlib import Path

from qveris_bench.execution.orchestrator import CellExecutionResult, RunOrchestrator
from qveris_bench.execution.resume import RunStateStore
from qveris_bench.models.enums import CellState
from qveris_bench.models.run import RunCell, RunPlan


def test_ac2_state_store_writes_atomically_and_resumes(tmp_path: Path) -> None:
    store = RunStateStore(tmp_path / "state.json")
    fingerprint = "a" * 64
    store.write(fingerprint, {"cell-1": CellState.INFRA_BLOCKED})

    assert store.resumable_keys(fingerprint) == ("cell-1",)
    assert store.path.read_text().startswith("{")


def test_ac2_state_store_rejects_a_different_fingerprint(tmp_path: Path) -> None:
    store = RunStateStore(tmp_path / "state.json")
    store.write("a" * 64, {"cell-1": CellState.INFRA_BLOCKED})

    try:
        store.read("b" * 64)
    except ValueError as exc:
        assert "fingerprint" in str(exc)
    else:
        raise AssertionError("resume must reject a changed frozen plan")


def test_ac2_resume_recovers_stale_running_cells(tmp_path: Path) -> None:
    async def run() -> None:
        plan = RunPlan(
            suite_id="suite-1",
            suite_fingerprint="a" * 64,
            cells=(
                RunCell(
                    run_key="cell-1",
                    case_id="case-1",
                    provider_id="p-1",
                    access_path_id="a-1",
                    mode="direct",
                    round=1,
                ),
            ),
        )
        store = RunStateStore(tmp_path / "state.json")
        store.write(plan.suite_fingerprint, {"cell-1": CellState.RUNNING})

        async def execute(_: RunCell) -> CellExecutionResult:
            return CellExecutionResult(CellState.COMPLETED)

        states = await RunOrchestrator(store, execute).run(plan)
        assert states["cell-1"] is CellState.COMPLETED

    asyncio.run(run())
