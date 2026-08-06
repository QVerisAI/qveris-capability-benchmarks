from __future__ import annotations

import json
from pathlib import Path

from qveris_bench.models.enums import CellState


class RunStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, suite_fingerprint: str, states: dict[str, CellState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = {
            "suite_fingerprint": suite_fingerprint,
            "states": {key: value.value for key, value in states.items()},
        }
        temporary.write_text(json.dumps(payload, sort_keys=True))
        temporary.replace(self.path)

    def read(self, suite_fingerprint: str) -> dict[str, CellState]:
        if not self.path.exists():
            return {}
        document = json.loads(self.path.read_text())
        if document["suite_fingerprint"] != suite_fingerprint:
            raise ValueError("run state fingerprint does not match the frozen plan")
        values = document["states"]
        return {key: CellState(value) for key, value in values.items()}

    def resumable_keys(self, suite_fingerprint: str) -> tuple[str, ...]:
        return tuple(
            key
            for key, value in self.read(suite_fingerprint).items()
            if value is CellState.INFRA_BLOCKED
        )
