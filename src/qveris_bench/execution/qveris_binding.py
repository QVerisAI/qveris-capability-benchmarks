from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId


class QverisDirectBindingError(ValueError):
    pass


class QverisDirectBinding(FrozenModel):
    version: SemanticVersion
    access_path_id: StableId
    provider_id: StableId
    discovery_query: str = Field(min_length=1)
    discovery_digest: EvidenceRef
    tool_id: str = Field(min_length=1)
    parameters: dict[str, Any]


def load_qveris_direct_binding(path: Path, expected_digest: str) -> QverisDirectBinding:
    try:
        content = path.read_bytes()
        if sha256_digest(content) != expected_digest:
            raise QverisDirectBindingError("QVeris direct binding digest mismatch")
        return QverisDirectBinding.model_validate_json(content)
    except (OSError, ValidationError, ValueError) as exc:
        if isinstance(exc, QverisDirectBindingError):
            raise
        raise QverisDirectBindingError("invalid QVeris direct binding") from exc
