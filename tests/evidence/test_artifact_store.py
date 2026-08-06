from pathlib import Path

import pytest

from qveris_bench.evidence.store import (
    ArtifactStoreError,
    PublicArtifactStore,
    RawArtifactStore,
)


def test_ac2_raw_and_public_artifacts_have_independent_digests(tmp_path: Path) -> None:
    raw = RawArtifactStore(tmp_path / "private-raw", repository_root=tmp_path / "repo")
    public = PublicArtifactStore(tmp_path / "repo" / "evidence" / "release-1")

    raw_record = raw.persist("cell-1", b'{"token":"secret"}')
    public_record = public.persist("cell-1", b'{"token":"[REDACTED]"}')

    assert raw_record.digest != public_record.digest
    assert raw_record.path.read_bytes() != public_record.path.read_bytes()


def test_ac2_raw_store_rejects_a_repository_path(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    with pytest.raises(ArtifactStoreError, match="outside the repository"):
        RawArtifactStore(repository_root / "evidence" / "raw", repository_root)


def test_ac2_public_store_redacts_before_persistence(tmp_path: Path) -> None:
    public = PublicArtifactStore(tmp_path / "repo" / "evidence" / "release-1")
    token = "api_" + "key"

    record = public.persist("cell-1", f"{token}=value-secret".encode())

    assert b"value-secret" not in record.path.read_bytes()
