from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qveris_bench.articles.publication import reproduce_article_publication
from qveris_bench.models.publication import PublicationPackageSpec


class GovernmentBondYieldPublicationAdapter:
    adapter_id = "govt-bond-yield-v1"
    adapter_version = "1.0.0"
    cap_id = "govt-bond-yield"

    def reproduce(
        self,
        *,
        repository_root: Path,
        package_path: Path,
        package: PublicationPackageSpec,
        document: Mapping[str, Any],
        output_dir: Path,
    ) -> tuple[str, ...]:
        return reproduce_article_publication(
            repository_root=repository_root,
            package=package,
            document=document,
        )
