from pathlib import Path

from qveris_bench.execution.resume import RunStateStore
from qveris_bench.models.enums import CellState


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
