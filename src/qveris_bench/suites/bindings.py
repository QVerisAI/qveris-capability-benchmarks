from __future__ import annotations

from pathlib import Path
from typing import Any

from qveris_bench.models.provider import AccessPath
from qveris_bench.yaml_io import load_yaml_mapping


class ProviderBindingError(ValueError):
    pass


def validate_provider_bindings(
    path: Path, access_paths: tuple[AccessPath, ...]
) -> None:
    data = load_yaml_mapping(path)
    bindings = data.get("access_paths")
    if not isinstance(bindings, list):
        raise ProviderBindingError("access_paths must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, dict) or not all(
            isinstance(binding.get(name), str)
            for name in ("access_path_id", "provider_id", "canonical_interface")
        ):
            raise ProviderBindingError("each provider binding must identify its path")
        path_id = binding["access_path_id"]
        if path_id in by_id:
            raise ProviderBindingError(f"duplicate provider binding: {path_id}")
        by_id[path_id] = binding
    resolved_ids = {access_path.access_path_id for access_path in access_paths}
    if set(by_id) != resolved_ids:
        raise ProviderBindingError("provider bindings do not match suite access paths")
    for access_path in access_paths:
        binding = by_id[access_path.access_path_id]
        if (
            binding["provider_id"] != access_path.provider_id
            or binding["canonical_interface"] != access_path.canonical_interface
        ):
            raise ProviderBindingError(
                "provider binding does not match registry: "
                f"{access_path.access_path_id}"
            )
