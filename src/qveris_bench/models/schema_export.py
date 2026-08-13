from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from qveris_bench.models.cap import CapDefinition
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.provider import AccessPath, ProviderProfile
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunPlan, TaskOutcome
from qveris_bench.models.suite import BenchmarkSuite

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "access-path.schema.json": AccessPath,
    "benchmark-release.schema.json": BenchmarkRelease,
    "benchmark-suite.schema.json": BenchmarkSuite,
    "cap-definition.schema.json": CapDefinition,
    "evidence-bundle.schema.json": EvidenceBundle,
    "provider-profile.schema.json": ProviderProfile,
    "run-plan.schema.json": RunPlan,
    "task-outcome.schema.json": TaskOutcome,
}


def _schema_bytes(model: type[BaseModel]) -> bytes:
    schema = model.model_json_schema(mode="validation")
    return (json.dumps(schema, indent=2, sort_keys=True) + "\n").encode()


def export_schemas(output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for filename, model in SCHEMA_MODELS.items():
        target = output_dir / filename
        target.write_bytes(_schema_bytes(model))
        exported.append(target)
    return tuple(exported)


def check_schemas(output_dir: Path) -> bool:
    expected_names = set(SCHEMA_MODELS)
    actual_names = {path.name for path in output_dir.glob("*.schema.json")}
    if actual_names != expected_names:
        return False
    return all(
        (output_dir / filename).read_bytes() == _schema_bytes(model)
        for filename, model in SCHEMA_MODELS.items()
    )
