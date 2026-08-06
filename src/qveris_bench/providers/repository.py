from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError, model_validator

from qveris_bench.models.base import FrozenModel
from qveris_bench.models.provider import AccessPath, ProviderProfile
from qveris_bench.providers.credentials import (
    CredentialReferenceError,
    validate_credential_reference,
)
from qveris_bench.providers.qualification import (
    QualificationDecision,
    check_frozen_cohort,
)


class ProviderValidationError(ValueError):
    pass


class DuplicateProviderIdentityError(ValueError):
    pass


class ProviderRegistryEntry(FrozenModel):
    provider: ProviderProfile
    access_paths: tuple[AccessPath, ...] = Field(min_length=1)
    qualification: QualificationDecision | None = None

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    @model_validator(mode="after")
    def validate_access_paths(self) -> ProviderRegistryEntry:
        path_ids: set[str] = set()
        for access_path in self.access_paths:
            if access_path.provider_id != self.provider.provider_id:
                raise ValueError(
                    f"access path {access_path.access_path_id} references "
                    f"{access_path.provider_id}, expected {self.provider.provider_id}"
                )
            if access_path.access_path_id in path_ids:
                raise ValueError(f"duplicate Access Path {access_path.access_path_id}")
            path_ids.add(access_path.access_path_id)
            for reference in access_path.credential_env:
                validate_credential_reference(reference)
        return self


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProviderValidationError(
            f"{path}: unable to load provider YAML: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ProviderValidationError(f"{path}: provider YAML root must be a mapping")
    return loaded


class ProviderRegistryRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, path: Path) -> ProviderRegistryEntry:
        try:
            return ProviderRegistryEntry.model_validate(_load_yaml_mapping(path))
        except (ValidationError, CredentialReferenceError) as exc:
            raise ProviderValidationError(
                f"{path}: invalid provider definition: {exc}"
            ) from exc

    def list(self) -> tuple[ProviderRegistryEntry, ...]:
        records: dict[str, ProviderRegistryEntry] = {}
        access_paths: set[str] = set()
        for path in sorted(self.root.rglob("provider.yaml")):
            relative = path.relative_to(self.root)
            if any(part.startswith("_") for part in relative.parts[:-1]):
                continue
            record = self.load(path)
            if record.provider_id in records:
                raise DuplicateProviderIdentityError(
                    f"duplicate Provider {record.provider_id}"
                )
            for access_path in record.access_paths:
                if access_path.access_path_id in access_paths:
                    raise DuplicateProviderIdentityError(
                        f"duplicate Access Path {access_path.access_path_id}"
                    )
                access_paths.add(access_path.access_path_id)
            records[record.provider_id] = record
        return tuple(records[key] for key in sorted(records))

    def cohort_check(self) -> tuple[ProviderRegistryEntry, ...]:
        records = self.list()
        check_frozen_cohort(records)
        return records


def qualify_provider_file(
    path: Path, decision: QualificationDecision
) -> ProviderRegistryEntry:
    repository = ProviderRegistryRepository(path.parent)
    repository.load(path)
    data = _load_yaml_mapping(path)
    data["qualification"] = decision.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return repository.load(path)
