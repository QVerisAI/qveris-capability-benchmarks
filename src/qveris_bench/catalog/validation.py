from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from qveris_bench.models.cap import CapDefinition
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class CapValidationError(ValueError):
    pass


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        return load_yaml_mapping(path)
    except YamlDocumentError as exc:
        raise CapValidationError(f"{path}: unable to load CAP YAML: {exc}") from exc


def validate_cap_file(path: Path) -> CapDefinition:
    try:
        return CapDefinition.model_validate(_load_yaml_mapping(path))
    except ValidationError as exc:
        raise CapValidationError(f"{path}: invalid CAP definition: {exc}") from exc
