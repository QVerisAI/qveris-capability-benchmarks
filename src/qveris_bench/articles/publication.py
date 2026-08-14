from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qveris_bench.articles.factory_v2 import reproduce_article_package
from qveris_bench.articles.writer import WriterInputBuildError, build_writer_input
from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.profiles.selection import (
    SelectionSnapshotBuildError,
    build_selection_snapshot,
)
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)


def reproduce_article_publication(
    *,
    repository_root: Path,
    package: PublicationPackageSpec,
    document: Mapping[str, Any],
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
        writer_input = resolve_repository_path(
            repository_root, str(artifacts["writer_input"])
        )
        editorial = resolve_repository_path(
            repository_root, str(artifacts["editorial"])
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
    _validate_snapshot_release_refs(rebuilt_snapshot.snapshot, document)
    if snapshot.read_bytes() != rebuilt_snapshot.json_bytes:
        raise PublicationReproductionError("selection snapshot differs from inputs")
    try:
        rebuilt_writer_input = build_writer_input(
            snapshot, profile, repository_root
        )
    except WriterInputBuildError as exc:
        raise PublicationReproductionError(
            "writer input cannot be rebuilt"
        ) from exc
    if writer_input.read_bytes() != rebuilt_writer_input.json_bytes:
        raise PublicationReproductionError(
            "writer input differs from public evidence"
        )
    reproduce_article_package(
        snapshot,
        profile,
        article_dir,
        writer_input_path=writer_input,
        editorial_path=editorial,
    )
    relative_article_dir = os.path.relpath(article_dir, published_guide.parent)
    projected = (article_dir / "article.md").read_text(encoding="utf-8").replace(
        "](charts/",
        f"]({relative_article_dir}/charts/",
    )
    if published_guide.read_text(encoding="utf-8") != projected:
        raise PublicationReproductionError(
            "published guide differs from article package"
        )
    return ("selection_snapshot", "charts", "article_facts", "links")


def _validate_snapshot_release_refs(
    snapshot: Any,
    document: Mapping[str, Any],
) -> None:
    try:
        cap_release_digest = document["release"]["digest"]
        market_release_digest = document["market_coverage_release"]["digest"]
    except (KeyError, TypeError) as exc:
        raise PublicationReproductionError(
            "publication release references are incomplete"
        ) from exc
    if (
        snapshot.cap_release_digest != cap_release_digest
        or snapshot.market_coverage_release_digest != market_release_digest
    ):
        raise PublicationReproductionError(
            "selection snapshot release references differ from publication package"
        )
