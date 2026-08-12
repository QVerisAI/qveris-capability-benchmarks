from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from qveris_bench.models.publication import PublicationPackageSpec


class PublicationAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    cap_id: str

    def reproduce(
        self,
        *,
        repository_root: Path,
        package_path: Path,
        package: PublicationPackageSpec,
        document: Mapping[str, Any],
        output_dir: Path,
    ) -> tuple[str, ...]: ...
