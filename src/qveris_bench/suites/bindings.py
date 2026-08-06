from __future__ import annotations

from pathlib import Path

from pydantic import Field, HttpUrl, ValidationError

from qveris_bench.models.base import FrozenModel, StableId
from qveris_bench.models.provider import AccessPath
from qveris_bench.yaml_io import load_yaml_mapping


class ProviderBindingError(ValueError):
    pass


class ProviderBinding(FrozenModel):
    access_path_id: StableId
    provider_id: StableId
    canonical_interface: str = Field(min_length=1)
    official_source: HttpUrl


class ProviderBindings(FrozenModel):
    access_paths: tuple[ProviderBinding, ...] = Field(min_length=1)


def load_provider_bindings(path: Path) -> ProviderBindings:
    try:
        bindings = ProviderBindings.model_validate(load_yaml_mapping(path))
    except (OSError, ValidationError, ValueError) as exc:
        raise ProviderBindingError(f"invalid provider bindings: {path}") from exc
    if len({item.access_path_id for item in bindings.access_paths}) != len(
        bindings.access_paths
    ):
        raise ProviderBindingError("duplicate provider binding")
    return bindings


def validate_provider_bindings(
    bindings: ProviderBindings, access_paths: tuple[AccessPath, ...]
) -> None:
    by_id = {binding.access_path_id: binding for binding in bindings.access_paths}
    resolved_ids = {access_path.access_path_id for access_path in access_paths}
    if set(by_id) != resolved_ids:
        raise ProviderBindingError("provider bindings do not match suite access paths")
    for access_path in access_paths:
        binding = by_id[access_path.access_path_id]
        if (
            binding.provider_id != access_path.provider_id
            or binding.canonical_interface != access_path.canonical_interface
            or str(binding.official_source) != str(access_path.official_source)
        ):
            raise ProviderBindingError(
                "provider binding does not match registry: "
                f"{access_path.access_path_id}"
            )
