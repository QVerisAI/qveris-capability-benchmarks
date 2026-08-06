from pathlib import Path

from qveris_bench.execution.resume import RunStateStore
from qveris_bench.models.enums import CellState


def test_ac2_state_store_writes_atomically_and_resumes(tmp_path: Path) -> None:
    store = RunStateStore(tmp_path / "state.json")
    store.write({"cell-1": CellState.INFRA_BLOCKED})

    assert store.resumable_keys() == ("cell-1",)
    assert store.path.read_text().startswith("{")
