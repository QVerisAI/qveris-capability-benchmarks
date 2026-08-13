from __future__ import annotations

import hashlib
import json
import tempfile
from importlib.metadata import entry_points
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from qveris_bench.models.publication import (
    PublicationPackageManifest,
    PublicationReleaseRef,
    PublicationReproductionReport,
)
from qveris_bench.publications.protocol import PublicationAdapter
from qveris_bench.releases.replay import ReleaseReplayError, replay_release_dir
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping

_ADAPTER_GROUP = "qveris_bench.publication_adapters"
_EXPECTED_CHECKS = (
    "selection_snapshot",
    "charts",
    "article_facts",
    "links",
)


class PublicationReproductionError(ValueError):
    pass


def reproduce_publication_package(
    package_path: Path,
    *,
    expected_package_digest: str | None = None,
) -> PublicationReproductionReport:
    try:
        resolved_package = package_path.resolve(strict=True)
        repository_root = _repository_root(resolved_package)
        document = load_yaml_mapping(resolved_package)
        manifest = PublicationPackageManifest.model_validate(document)
    except (OSError, ValidationError, YamlDocumentError) as exc:
        raise PublicationReproductionError(
            f"invalid publication package: {exc}"
        ) from exc

    release_dirs: list[Path] = []
    release_ids: set[str] = set()
    for section_name in manifest.publication_package.release_sections:
        section = document.get(section_name)
        if not isinstance(section, dict):
            raise PublicationReproductionError(
                f"missing publication release section: {section_name}"
            )
        try:
            release_ref = PublicationReleaseRef.model_validate(section)
        except ValidationError as exc:
            raise PublicationReproductionError(
                f"invalid publication release section: {section_name}"
            ) from exc
        release_dir = resolve_repository_path(repository_root, release_ref.directory)
        try:
            replayed = replay_release_dir(
                release_dir,
                expected_digest=release_ref.digest,
            )
        except ReleaseReplayError as exc:
            raise PublicationReproductionError(
                f"release reproduction failed for {section_name}: {exc}"
            ) from exc
        if replayed.release_id in release_ids:
            raise PublicationReproductionError(
                "publication release identities must be unique"
            )
        release_ids.add(replayed.release_id)
        release_dirs.append(release_dir)

    package_digest = _package_digest(
        resolved_package,
        repository_root,
        document,
        release_dirs,
    )
    if (
        expected_package_digest is not None
        and package_digest != expected_package_digest
    ):
        raise PublicationReproductionError(
            "publication package digest does not match expected digest"
        )

    adapter = _load_adapter(manifest.publication_package.adapter_id)
    if (
        adapter.adapter_version != manifest.publication_package.adapter_version
        or adapter.cap_id != manifest.publication_package.cap_id
    ):
        raise PublicationReproductionError(
            "publication adapter version or CAP identity mismatch"
        )
    with tempfile.TemporaryDirectory(prefix="qveris-publication-") as temporary:
        checks = adapter.reproduce(
            repository_root=repository_root,
            package_path=resolved_package,
            package=manifest.publication_package,
            document=document,
            output_dir=Path(temporary),
        )
    if checks != _EXPECTED_CHECKS:
        raise PublicationReproductionError(
            "publication adapter did not complete every required check"
        )
    return PublicationReproductionReport(
        package_id=manifest.publication_package.package_id,
        package_digest=package_digest,
        status="verified",
        release_count=len(release_dirs),
        checks=("releases", *checks),
        canonical_chart_bytes_verified=False,
    )


def resolve_repository_path(repository_root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PublicationReproductionError(
            "publication path must stay inside the repository"
        )
    resolved_root = repository_root.resolve(strict=True)
    try:
        resolved = (resolved_root / candidate).resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise PublicationReproductionError(
            "publication path must stay inside the repository"
        ) from exc
    return resolved


def _repository_root(package_path: Path) -> Path:
    for candidate in package_path.parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "cap_packs"
        ).is_dir():
            return candidate
    raise PublicationReproductionError(
        "publication package must be inside a benchmark repository"
    )


def _load_adapter(adapter_id: str) -> PublicationAdapter:
    matches = tuple(entry_points(group=_ADAPTER_GROUP, name=adapter_id))
    if len(matches) != 1:
        raise PublicationReproductionError(
            f"publication adapter must resolve exactly once: {adapter_id}"
        )
    loaded = matches[0].load()
    adapter = loaded() if isinstance(loaded, type) else loaded
    for attribute in ("adapter_id", "adapter_version", "cap_id", "reproduce"):
        if not hasattr(adapter, attribute):
            raise PublicationReproductionError(
                f"invalid publication adapter: {adapter_id}"
            )
    return cast(PublicationAdapter, adapter)


def report_json(report: PublicationReproductionReport) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2) + "\n"


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _package_digest(
    package_path: Path,
    repository_root: Path,
    document: dict[str, object],
    release_dirs: list[Path],
) -> str:
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict):
        raise PublicationReproductionError("publication artifacts must be a mapping")
    targets = {package_path, *release_dirs}
    for value in artifacts.values():
        values = value if isinstance(value, list) else [value]
        for path_value in values:
            if isinstance(path_value, str) and not path_value.startswith("sha256:"):
                targets.add(resolve_repository_path(repository_root, path_value))
    files: set[Path] = set()
    for target in targets:
        if target.is_dir():
            files.update(item for item in target.rglob("*") if item.is_file())
        else:
            files.add(target)
    digest = hashlib.sha256()
    for item in sorted(files):
        resolved = item.resolve(strict=True)
        try:
            relative = resolved.relative_to(repository_root.resolve(strict=True))
        except ValueError as exc:
            raise PublicationReproductionError(
                "publication path must stay inside the repository"
            ) from exc
        digest.update(str(relative).encode())
        digest.update(b"\0")
        digest.update(resolved.read_bytes())
    return f"sha256:{digest.hexdigest()}"
