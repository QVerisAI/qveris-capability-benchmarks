from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qveris_bench.articles.factory import reproduce_article_package
from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.profiles.selection import (
    SelectionSnapshotBuildError,
    build_selection_snapshot,
)
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)


class CorporateActionsPublicationAdapter:
    adapter_id = "corporate-actions-v1"
    adapter_version = "1.0.0"
    cap_id = "corporate-actions"

    def reproduce(
        self,
        *,
        repository_root: Path,
        package_path: Path,
        package: PublicationPackageSpec,
        document: Mapping[str, Any],
        output_dir: Path,
    ) -> tuple[str, ...]:
        artifacts = document.get("artifacts")
        if not isinstance(artifacts, Mapping):
            raise PublicationReproductionError("publication artifacts are missing")
        try:
            snapshot = resolve_repository_path(
                repository_root, str(artifacts["selection_snapshot"])
            )
            snapshot_input = resolve_repository_path(
                repository_root, str(artifacts["selection_snapshot_input"])
            )
            profile = resolve_repository_path(
                repository_root, str(artifacts["publication_profile"])
            )
            article_dir = resolve_repository_path(
                repository_root, str(artifacts["article_package"])
            )
        except (KeyError, TypeError) as exc:
            raise PublicationReproductionError(
                "publication artifacts are incomplete"
            ) from exc
        try:
            rebuilt_snapshot = build_selection_snapshot(snapshot_input, repository_root)
        except SelectionSnapshotBuildError as exc:
            raise PublicationReproductionError(
                "selection snapshot cannot be rebuilt"
            ) from exc
        if snapshot.read_bytes() != rebuilt_snapshot.json_bytes:
            raise PublicationReproductionError("selection snapshot differs from inputs")
        reproduce_article_package(snapshot, profile, article_dir)
        return ("selection_snapshot", "charts", "article_facts", "links")
