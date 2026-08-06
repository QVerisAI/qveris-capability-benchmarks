from __future__ import annotations

from pathlib import Path

from qveris_bench.catalog.validation import validate_cap_file
from qveris_bench.models.cap import CapDefinition


class DuplicateCapError(ValueError):
    pass


class CapCatalogRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self) -> tuple[CapDefinition, ...]:
        caps: dict[tuple[str, str], CapDefinition] = {}
        for path in sorted(self.root.rglob("cap.yaml")):
            relative = path.relative_to(self.root)
            if any(part.startswith("_") for part in relative.parts[:-1]):
                continue
            cap = validate_cap_file(path)
            identity = (cap.cap_id, cap.version)
            if identity in caps:
                raise DuplicateCapError(f"duplicate CAP {cap.cap_id}@{cap.version}")
            caps[identity] = cap
        return tuple(caps[key] for key in sorted(caps))
