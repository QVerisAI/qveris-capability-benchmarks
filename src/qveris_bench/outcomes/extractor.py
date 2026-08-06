from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from qveris_bench.models.base import EvidenceRef, SemanticVersion
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
    field_types = schema.get("field_types", {})
    additional_fields = schema.get("additional_fields", False)
    valid_fields = isinstance(required_fields, list) and all(
        isinstance(item, str) for item in required_fields
    )
    if not valid_fields:
        raise ExtractionError("required_fields must be a list of strings")
    missing = [field for field in required_fields if field not in facts]
    if missing:
        raise ExtractionError("missing observation fields: " + ", ".join(missing))
    if not isinstance(field_types, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in field_types.items()
    ):
        raise ExtractionError("field_types must map field names to type names")
    if not additional_fields:
        unknown = sorted(set(facts) - set(required_fields) - set(field_types))
        if unknown:
            raise ExtractionError("unknown observation fields: " + ", ".join(unknown))
    for field, type_name in field_types.items():
        value = facts.get(field)
        valid_type = (
            (type_name == "string" and isinstance(value, str))
            or (
                type_name == "number"
                and isinstance(
                    value,
                    (
                        int,
                        float,
                    ),
                )
                and not isinstance(value, bool)
            )
            or (type_name == "boolean" and isinstance(value, bool))
        )
        if not valid_type:
            raise ExtractionError(f"invalid observation type: {field}")
    try:
        TypeAdapter(EvidenceRef).validate_python(evidence_ref)
        TypeAdapter(SemanticVersion).validate_python(extractor_version)
    except ValidationError as exc:
        raise ExtractionError("observation provenance is invalid") from exc
    return Observation(dict(facts), evidence_ref, extractor_version)
