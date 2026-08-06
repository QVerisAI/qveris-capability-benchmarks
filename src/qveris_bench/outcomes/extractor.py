from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qveris_bench.yaml_io import load_yaml_mapping


class ExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class Observation:
    facts: dict[str, Any]
    evidence_ref: str
    extractor_version: str


def extract_observation(
    schema_path: Path,
    facts: dict[str, Any],
    evidence_ref: str,
    extractor_version: str,
) -> Observation:
    schema = load_yaml_mapping(schema_path)
    required_fields = schema.get("required_fields", [])
    valid_fields = isinstance(required_fields, list) and all(
        isinstance(item, str) for item in required_fields
    )
    if not valid_fields:
        raise ExtractionError("required_fields must be a list of strings")
    missing = [field for field in required_fields if field not in facts]
    if missing:
        raise ExtractionError("missing observation fields: " + ", ".join(missing))
    if not evidence_ref.startswith("sha256:"):
        raise ExtractionError("observation requires an evidence digest")
    return Observation(dict(facts), evidence_ref, extractor_version)
