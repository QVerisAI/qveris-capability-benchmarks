from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qveris_bench.evidence.hashing import sha256_digest


class ArtifactStoreError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    digest: str
    path: Path


class _ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def persist(self, artifact_id: str, content: bytes) -> ArtifactRecord:
        if not artifact_id or Path(artifact_id).name != artifact_id:
            raise ArtifactStoreError("artifact ID must be a single non-empty filename")
        self.root.mkdir(parents=True, exist_ok=True)
        digest = sha256_digest(content)
        target = self.root / f"{artifact_id}-{digest.removeprefix('sha256:')}.json"
        target.write_bytes(content)
        return ArtifactRecord(artifact_id=artifact_id, digest=digest, path=target)


class RawArtifactStore(_ArtifactStore):
    def __init__(self, root: Path, repository_root: Path) -> None:
        resolved_root = root.resolve()
        resolved_repository = repository_root.resolve()
        if resolved_root.is_relative_to(resolved_repository):
            raise ArtifactStoreError(
                "raw evidence store must live outside the repository"
            )
        super().__init__(resolved_root)


class PublicArtifactStore(_ArtifactStore):
    pass
