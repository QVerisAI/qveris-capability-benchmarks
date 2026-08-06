from __future__ import annotations

import json
from pathlib import Path

from qveris_bench.models.enums import CellState


class RunStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, states: dict[str, CellState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = {key: value.value for key, value in states.items()}
        temporary.write_text(json.dumps(payload, sort_keys=True))
        temporary.replace(self.path)

    def read(self) -> dict[str, CellState]:
        if not self.path.exists():
            return {}
        values = json.loads(self.path.read_text())
        return {key: CellState(value) for key, value in values.items()}

    def resumable_keys(self) -> tuple[str, ...]:
        return tuple(
            key
            for key, value in self.read().items()
            if value is CellState.INFRA_BLOCKED
        )
