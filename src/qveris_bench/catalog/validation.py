from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from qveris_bench.models.cap import CapDefinition


class CapValidationError(ValueError):
    pass


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CapValidationError(f"{path}: unable to load CAP YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise CapValidationError(f"{path}: CAP YAML root must be a mapping")
    return loaded


def validate_cap_file(path: Path) -> CapDefinition:
    try:
        return CapDefinition.model_validate(_load_yaml_mapping(path))
    except ValidationError as exc:
        raise CapValidationError(f"{path}: invalid CAP definition: {exc}") from exc
