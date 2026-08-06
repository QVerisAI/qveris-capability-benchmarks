from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId


class QverisDirectBindingError(ValueError):
    pass


class QverisDirectBinding(FrozenModel):
    binding_id: StableId | None = None
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


def load_registered_qveris_direct_binding(
    registry_path: Path, binding_id: str
) -> QverisDirectBinding:
    try:
        document = json.loads(registry_path.read_text())
        bindings = document.get("bindings", [])
        if not isinstance(bindings, list):
            raise QverisDirectBindingError("invalid QVeris direct binding registry")
        matches = [
            QverisDirectBinding.model_validate(item)
            for item in bindings
            if isinstance(item, dict) and item.get("binding_id") == binding_id
        ]
    except (OSError, ValidationError, ValueError) as exc:
        if isinstance(exc, QverisDirectBindingError):
            raise
        raise QverisDirectBindingError(
            "invalid QVeris direct binding registry"
        ) from exc
    if len(matches) != 1:
        raise QverisDirectBindingError("unknown binding")
    return matches[0]
