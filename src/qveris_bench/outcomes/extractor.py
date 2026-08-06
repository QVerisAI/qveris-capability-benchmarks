from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
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
    *,
    negative_control: bool = False,
) -> Observation:
    schema = load_yaml_mapping(schema_path)
    if negative_control:
        schema = schema.get("negative_control", {})
        if not isinstance(schema, dict):
            raise ExtractionError("negative_control must be a mapping")
    required_fields = schema.get("required_fields", [])
    field_types = schema.get("field_types", {})
    field_constraints = schema.get("field_constraints", {})
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
    if not isinstance(field_constraints, dict):
        raise ExtractionError("field_constraints must be a mapping")
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
            or (type_name == "array" and isinstance(value, list))
            or (
                type_name == "number_array"
                and isinstance(value, list)
                and all(
                    isinstance(item, (int, float))
                    and not isinstance(item, bool)
                    and isfinite(item)
                    for item in value
                )
            )
        )
        if not valid_type:
            raise ExtractionError(f"invalid observation type: {field}")
        constraints = field_constraints.get(field, {})
        if not isinstance(constraints, dict):
            raise ExtractionError(f"invalid observation constraints: {field}")
        if constraints.get("non_empty") and not value:
            raise ExtractionError(f"empty observation field: {field}")
        same_length_as = constraints.get("same_length_as")
        if isinstance(same_length_as, str) and isinstance(value, list):
            peer = facts.get(same_length_as)
            if not isinstance(peer, list) or len(value) != len(peer):
                raise ExtractionError(f"unaligned observation field: {field}")
        minimum = constraints.get("minimum")
        maximum = constraints.get("maximum")
        if isinstance(value, list) and all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in value
        ):
            if isinstance(minimum, (int, float)) and any(
                item < minimum for item in value
            ):
                raise ExtractionError(f"below-minimum observation field: {field}")
            if isinstance(maximum, (int, float)) and any(
                item > maximum for item in value
            ):
                raise ExtractionError(f"above-maximum observation field: {field}")
        if constraints.get("finite") and isinstance(value, (int, float)):
            if not isfinite(value):
                raise ExtractionError(f"non-finite observation field: {field}")
        if constraints.get("positive") and isinstance(value, (int, float)):
            if value <= 0:
                raise ExtractionError(f"non-positive observation field: {field}")
        if constraints.get("iso8601"):
            try:
                timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ExtractionError(
                    f"invalid observation timestamp: {field}"
                ) from exc
            max_age = constraints.get("max_age_seconds")
            if isinstance(max_age, int) and timestamp.tzinfo is not None:
                age = (datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds()
                if age > max_age:
                    raise ExtractionError(f"stale observation field: {field}")
    try:
        TypeAdapter(EvidenceRef).validate_python(evidence_ref)
        TypeAdapter(SemanticVersion).validate_python(extractor_version)
    except ValidationError as exc:
        raise ExtractionError("observation provenance is invalid") from exc
    return Observation(dict(facts), evidence_ref, extractor_version)
