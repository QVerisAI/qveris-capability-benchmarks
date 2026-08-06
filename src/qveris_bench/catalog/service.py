from __future__ import annotations

from pathlib import Path

from qveris_bench.catalog.repository import CapCatalogRepository
from qveris_bench.catalog.validation import validate_cap_file
from qveris_bench.models.cap import CapDefinition


class CapCatalogService:
    def list(self, root: Path) -> tuple[CapDefinition, ...]:
        return CapCatalogRepository(root).list()

    def validate(self, path: Path) -> CapDefinition:
        return validate_cap_file(path)
