from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field, ValidationError, model_validator

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import AccessPathType
from qveris_bench.suites.compiler import compile_suite


class DirectBindingRegistryError(ValueError):
    pass


class DirectBinding(FrozenModel):
    binding_id: StableId
    suite_id: StableId
    version: SemanticVersion
    case_id: StableId
    access_path_id: StableId
    provider_id: StableId
    transport: AccessPathType
    source_digest: EvidenceRef
    tool_id: str = Field(min_length=1)
    parameters: dict[str, object]
    discovery_query: str | None = Field(default=None, min_length=1)
    request_identity: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_transport_contract(self) -> DirectBinding:
        if self.transport not in {
            AccessPathType.NATIVE_MCP,
            AccessPathType.QVERIS_CONNECTOR,
        }:
            raise ValueError("Direct binding transport is unsupported")
        if (
            self.transport is AccessPathType.QVERIS_CONNECTOR
            and self.discovery_query is None
        ):
            raise ValueError("QVeris Direct binding requires discovery_query")
        if (
            self.transport is AccessPathType.NATIVE_MCP
            and self.discovery_query is not None
        ):
            raise ValueError("Native MCP binding cannot use QVeris discovery")
        return self


class DirectBindingRegistry(FrozenModel):
    bindings: tuple[DirectBinding, ...] = Field(min_length=1)

    def for_cell(self, case_id: str, access_path_id: str) -> DirectBinding:
        matches = [
            binding
            for binding in self.bindings
            if binding.case_id == case_id and binding.access_path_id == access_path_id
        ]
        if len(matches) != 1:
            raise DirectBindingRegistryError("cell must resolve to one Direct binding")
        return matches[0]


def load_direct_binding_registry(path: Path) -> DirectBindingRegistry:
    try:
        registry = DirectBindingRegistry.model_validate_json(path.read_text())
    except (OSError, ValidationError, ValueError) as exc:
        raise DirectBindingRegistryError("invalid Direct binding registry") from exc
    ids = [binding.binding_id for binding in registry.bindings]
    if len(ids) != len(set(ids)):
        raise DirectBindingRegistryError("duplicate Direct binding ID")
    return registry


def validate_direct_binding_registry(
    registry: DirectBindingRegistry,
    suite_path: Path,
    cases_path: Path,
    providers_root: Path,
    *,
    cap_path: Path | None = None,
) -> None:
    compiled = compile_suite(suite_path, cases_path, providers_root, cap_path)
    paths = {path.access_path_id: path for path in compiled.access_paths}
    expected = {
        (cell.case_id, cell.access_path_id)
        for cell in compiled.run_plan.cells
        if cell.applicable
    }
    actual = {
        (binding.case_id, binding.access_path_id) for binding in registry.bindings
    }
    if len(actual) != len(registry.bindings) or actual != expected:
        raise DirectBindingRegistryError(
            "Direct bindings do not match applicable cell identities"
        )
    for binding in registry.bindings:
        if binding.suite_id != compiled.suite.suite_id:
            raise DirectBindingRegistryError("binding suite identity mismatch")
        path = paths[binding.access_path_id]
        if binding.provider_id != path.provider_id:
            raise DirectBindingRegistryError("binding Provider identity mismatch")
        if binding.transport is not path.path_type:
            raise DirectBindingRegistryError(
                "binding transport does not match Access Path"
            )


def direct_binding_registry_digest(path: Path) -> str:
    document = json.loads(path.read_text())
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return sha256_digest(canonical)
