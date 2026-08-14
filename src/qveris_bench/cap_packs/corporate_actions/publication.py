from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qveris_bench.articles.factory import reproduce_article_package
from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.publications.service import PublicationReproductionError, resolve_repository_path


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
            profile = resolve_repository_path(
                repository_root, str(artifacts["publication_profile"])
            )
            article_dir = resolve_repository_path(
                repository_root, str(artifacts["article_package"])
            )
        except (KeyError, TypeError) as exc:
            raise PublicationReproductionError("publication artifacts are incomplete") from exc
        reproduce_article_package(snapshot, profile, article_dir)
        return ("selection_snapshot", "charts", "article_facts", "links")
