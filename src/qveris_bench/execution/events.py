from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qveris_bench.evidence.redaction import redact_text
from qveris_bench.models.run import ObservationEvent


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event_type: str, details: dict[str, Any]) -> ObservationEvent:
        existing = self.read()
        safe_details = json.loads(redact_text(json.dumps(details)).text)
        event = ObservationEvent(
            sequence=len(existing),
            occurred_at=datetime.now(UTC),
            event_type=event_type,
            details=safe_details,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as stream:
            stream.write(event.model_dump_json() + "\n")
        return event

    def read(self) -> tuple[ObservationEvent, ...]:
        if not self.path.exists():
            return ()
        return tuple(
            ObservationEvent.model_validate_json(line)
            for line in self.path.read_text().splitlines()
        )
