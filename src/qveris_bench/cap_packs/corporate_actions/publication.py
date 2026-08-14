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
            published_guide = resolve_repository_path(
                repository_root, str(artifacts["published_guide"])
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
        _validate_snapshot_release_refs(rebuilt_snapshot, document)
        if snapshot.read_bytes() != rebuilt_snapshot.json_bytes:
            raise PublicationReproductionError("selection snapshot differs from inputs")
        reproduce_article_package(snapshot, profile, article_dir)
        package_article = article_dir / "article.md"
        projected = package_article.read_text(encoding="utf-8").replace(
            "](charts/",
            "](capability-seo/best-corporate-actions-apis/charts/",
        )
        if published_guide.read_text(encoding="utf-8") != projected:
            raise PublicationReproductionError(
                "published guide differs from article package"
            )
        return ("selection_snapshot", "charts", "article_facts", "links")


def _validate_snapshot_release_refs(
    rebuilt_snapshot: Any,
    document: Mapping[str, Any],
) -> None:
    try:
        cap_release_digest = document["release"]["digest"]
        market_release_digest = document["market_coverage_release"]["digest"]
    except (KeyError, TypeError) as exc:
        raise PublicationReproductionError(
            "publication release references are incomplete"
        ) from exc
    snapshot = rebuilt_snapshot.snapshot
    if (
        snapshot.cap_release_digest != cap_release_digest
        or snapshot.market_coverage_release_digest != market_release_digest
    ):
        raise PublicationReproductionError(
            "selection snapshot release references differ from publication package"
        )
