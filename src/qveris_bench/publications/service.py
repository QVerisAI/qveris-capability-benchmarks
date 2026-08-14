from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import platform
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from importlib.metadata import entry_points
from pathlib import Path
from typing import cast
from unittest.mock import patch

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
        if not (release_dir / "public-evidence-manifest.json").is_file():
            raise PublicationReproductionError(
                f"public evidence manifest is required for {section_name}"
            )
        try:
            replayed = replay_release_dir(
                release_dir,
                expected_digest=release_ref.digest,
            )
        except ReleaseReplayError as exc:
            raise PublicationReproductionError(
                f"release reproduction failed for {section_name}: {exc}"
            ) from exc
        _validate_public_evidence_file_set(release_dir, repository_root)
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
        adapter.adapter_id != manifest.publication_package.adapter_id
        or adapter.adapter_version != manifest.publication_package.adapter_version
        or adapter.cap_id != manifest.publication_package.cap_id
    ):
        raise PublicationReproductionError(
            "publication adapter identity, version, or CAP mismatch"
        )
    adapter_digest = _source_digest(
        repository_root,
        manifest.publication_package.adapter_sources,
    )
    if adapter_digest != manifest.publication_package.adapter_digest:
        raise PublicationReproductionError("publication adapter digest mismatch")
    with tempfile.TemporaryDirectory(prefix="qveris-publication-") as temporary:
        with _isolated_cache_environment(Path(temporary)):
            _validate_adapter_modules(
                adapter,
                repository_root,
                manifest.publication_package.adapter_sources,
            )
            try:
                with _offline_network():
                    checks = adapter.reproduce(
                        repository_root=repository_root,
                        package_path=resolved_package,
                        package=manifest.publication_package,
                        document=document,
                        output_dir=Path(temporary),
                    )
            except PublicationReproductionError:
                raise
            except (IndexError, KeyError, OSError, TypeError, ValueError) as exc:
                raise PublicationReproductionError(
                    f"publication validation failed: {exc}"
                ) from exc
    if checks != _EXPECTED_CHECKS:
        raise PublicationReproductionError(
            "publication adapter did not complete every required check"
        )
    return PublicationReproductionReport(
        package_id=manifest.publication_package.package_id,
        package_digest=package_digest,
        status=(
            "verified"
            if platform.system() == "Linux"
            else "verified_with_noncanonical_chart_bytes"
        ),
        release_count=len(release_dirs),
        checks=("releases", *checks),
        canonical_chart_bytes_verified=platform.system() == "Linux",
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
    package = document.get("publication_package")
    if not isinstance(package, dict):
        raise PublicationReproductionError("publication package must be a mapping")
    adapter_sources = package.get("adapter_sources")
    if not isinstance(adapter_sources, list):
        raise PublicationReproductionError("publication adapter sources must be a list")
    targets = {
        package_path,
        *release_dirs,
        *(resolve_repository_path(repository_root, value) for value in adapter_sources),
    }
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


def _source_digest(repository_root: Path, sources: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for source in sorted(sources):
        path = resolve_repository_path(repository_root, source)
        if not path.is_file():
            raise PublicationReproductionError(
                "publication adapter source must be a file"
            )
        digest.update(source.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _validate_adapter_modules(
    adapter: PublicationAdapter,
    repository_root: Path,
    sources: tuple[str, ...],
) -> None:
    module_names: set[str] = set()
    for source in sources:
        relative = Path(source)
        if not relative.parts or relative.parts[0] != "src" or relative.suffix != ".py":
            raise PublicationReproductionError(
                "publication adapter source must name a Python module under src"
            )
        module_parts = list(relative.with_suffix("").parts[1:])
        if module_parts[-1] == "__init__":
            module_parts.pop()
        module_name = ".".join(module_parts)
        module_names.add(module_name)
        module = importlib.import_module(module_name)
        loaded_source = inspect.getsourcefile(module)
        bound_source = resolve_repository_path(repository_root, source)
        if (
            loaded_source is None
            or Path(loaded_source).resolve(strict=True).read_bytes()
            != bound_source.read_bytes()
        ):
            raise PublicationReproductionError(
                "declared adapter module does not match its bound source"
            )
    if type(adapter).__module__ not in module_names:
        raise PublicationReproductionError(
            "loaded publication adapter is not a declared module"
        )


@contextmanager
def _offline_network() -> Iterator[None]:
    def deny_network(*args: object, **kwargs: object) -> None:
        raise PublicationReproductionError(
            "network access is disabled during publication reproduction"
        )

    targets = (
        "socket.create_connection",
        "socket.getaddrinfo",
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "socket.socket.sendto",
        "subprocess.Popen",
        "os.system",
        "os.popen",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, deny_network))
        yield


@contextmanager
def _isolated_cache_environment(directory: Path) -> Iterator[None]:
    cache = directory / "module-cache"
    cache.mkdir()
    names = ("MPLCONFIGDIR", "XDG_CACHE_HOME")
    previous = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ[name] = str(cache)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _validate_public_evidence_file_set(
    release_dir: Path,
    repository_root: Path,
) -> None:
    try:
        document = json.loads(
            (release_dir / "public-evidence-manifest.json").read_text(encoding="utf-8")
        )
        entries = document["evidence"]
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise PublicationReproductionError(
            "public evidence manifest is invalid"
        ) from exc
    if not isinstance(entries, list):
        raise PublicationReproductionError("public evidence manifest is invalid")
    expected: set[Path] = set()
    parents: set[Path] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise PublicationReproductionError("public evidence manifest is invalid")
        lexical = (repository_root / entry["path"]).absolute()
        path = resolve_repository_path(repository_root, entry["path"])
        if lexical.is_symlink() or lexical != path:
            raise PublicationReproductionError("public evidence file set differs")
        expected.add(lexical)
        parents.add(lexical.parent)
    if len(parents) != 1:
        raise PublicationReproductionError(
            "one Release must publish evidence in one directory"
        )
    evidence_root = parents.pop()
    observed: set[Path] = set()
    for path in evidence_root.rglob("*"):
        if path.is_symlink():
            raise PublicationReproductionError("public evidence file set differs")
        if path.is_file():
            observed.add(path.absolute())
    if observed != expected:
        raise PublicationReproductionError("public evidence file set differs")
