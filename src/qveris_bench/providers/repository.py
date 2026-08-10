from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError, model_validator

from qveris_bench.models.base import FrozenModel
from qveris_bench.models.provider import (
    AccessPath,
    ProviderProfile,
    QualificationDecision,
)
from qveris_bench.providers.qualification import check_frozen_cohort
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class ProviderValidationError(ValueError):
    pass


class DuplicateProviderIdentityError(ValueError):
    pass


class ProviderRegistryEntry(FrozenModel):
    provider: ProviderProfile
    access_paths: tuple[AccessPath, ...] = Field(min_length=1)

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
        for pricing in self.provider.official_pricing:
            if pricing.applies_to == "provider_wide":
                continue
            unknown = set(pricing.applies_to) - path_ids
            if unknown:
                raise ValueError(
                    f"pricing {pricing.pricing_id} references unknown Access Paths: "
                    + ", ".join(sorted(unknown))
                )
        return self


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        return load_yaml_mapping(path)
    except YamlDocumentError as exc:
        raise ProviderValidationError(
            f"{path}: unable to load provider YAML: {exc}"
        ) from exc


class ProviderRegistryRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, path: Path) -> ProviderRegistryEntry:
        try:
            return ProviderRegistryEntry.model_validate(_load_yaml_mapping(path))
        except ValidationError as exc:
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
        check_frozen_cohort(
            tuple(
                access_path for record in records for access_path in record.access_paths
            )
        )
        return records

    def validate_access_path_identities(
        self, identities: Iterable[tuple[str, str]]
    ) -> None:
        registered = self._access_paths_by_identity()
        unknown = set(identities) - registered.keys()
        if unknown:
            formatted = ", ".join(
                f"{provider}/{path}" for provider, path in sorted(unknown)
            )
            raise ProviderValidationError(f"unknown Provider/Access Path: {formatted}")

    def validate_direct_test_authorization(
        self, identities: Iterable[tuple[str, str]]
    ) -> None:
        requested = set(identities)
        self.validate_access_path_identities(requested)
        registered = self._access_paths_by_identity()
        denied: set[tuple[str, str]] = set()
        for identity in requested:
            qualification = registered[identity].qualification
            if qualification is None or qualification.disposition.value != "included":
                denied.add(identity)
        if denied:
            formatted = ", ".join(
                f"{provider}/{path}" for provider, path in sorted(denied)
            )
            raise ProviderValidationError(f"Direct Test is not authorized: {formatted}")

    def validate_agent_trial_eligibility(
        self, identities: Iterable[tuple[str, str]]
    ) -> None:
        requested = set(identities)
        self.validate_direct_test_authorization(requested)
        registered = self._access_paths_by_identity()
        ineligible = {
            identity
            for identity in requested
            if not registered[identity].agent_trial_eligible
        }
        if ineligible:
            formatted = ", ".join(
                f"{provider}/{path}" for provider, path in sorted(ineligible)
            )
            raise ProviderValidationError(f"Agent Trial is not eligible: {formatted}")

    def _access_paths_by_identity(self) -> dict[tuple[str, str], AccessPath]:
        return {
            (record.provider_id, path.access_path_id): path
            for record in self.list()
            for path in record.access_paths
        }


def qualify_provider_file(
    path: Path, access_path_id: str, decision: QualificationDecision
) -> ProviderRegistryEntry:
    repository = ProviderRegistryRepository(path.parent)
    repository.load(path)
    data = _load_yaml_mapping(path)
    access_paths = data.get("access_paths")
    if not isinstance(access_paths, list):
        raise ProviderValidationError(f"{path}: access_paths must be a list")
    for access_path in access_paths:
        if (
            isinstance(access_path, dict)
            and access_path.get("access_path_id") == access_path_id
        ):
            access_path["qualification"] = decision.model_dump(mode="json")
            break
    else:
        raise ProviderValidationError(f"{path}: unknown Access Path {access_path_id}")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return repository.load(path)
