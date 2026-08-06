from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import QualificationDisposition
from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.suites.loader import SuiteLoadError, load_suite


class QverisDirectBindingError(ValueError):
    pass


class QverisDirectBinding(FrozenModel):
    binding_id: StableId
    suite_id: StableId
    version: SemanticVersion
    access_path_id: StableId
    provider_id: StableId
    discovery_query: str = Field(min_length=1)
    discovery_digest: EvidenceRef
    tool_id: str = Field(min_length=1)
    parameters: dict[str, Any]


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


def validate_qveris_direct_binding(
    binding: QverisDirectBinding, suite_path: Path, providers_root: Path
) -> None:
    try:
        suite = load_suite(suite_path)
        if suite.suite_id != binding.suite_id:
            raise QverisDirectBindingError("binding suite does not match frozen suite")
        if binding.access_path_id not in suite.access_path_ids:
            raise QverisDirectBindingError("binding path is not in the frozen suite")
        records = ProviderRegistryRepository(providers_root).cohort_check()
        paths = {
            path.access_path_id: path
            for record in records
            for path in record.access_paths
        }
        path = paths.get(binding.access_path_id)
        if path is None or path.provider_id != binding.provider_id:
            raise QverisDirectBindingError(
                "binding provider does not match access path"
            )
        if path.qualification is None or (
            path.qualification.disposition is not QualificationDisposition.INCLUDED
        ):
            raise QverisDirectBindingError("binding path is not included")
    except (OSError, SuiteLoadError, ValueError) as exc:
        if isinstance(exc, QverisDirectBindingError):
            raise
        raise QverisDirectBindingError("invalid frozen suite binding") from exc
