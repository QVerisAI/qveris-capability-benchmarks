from __future__ import annotations

from pydantic import Field

from qveris_bench.execution.direct_binding import (
    DirectBindingRegistry,
    DirectBindingRegistryError,
)
from qveris_bench.models.base import FrozenModel
from qveris_bench.suites.compiler import CompiledSuite


class GovernmentBondRequestIdentity(FrozenModel):
    country: str = Field(pattern=r"^[A-Z]{2}$")
    tenor: str = Field(pattern=r"^10Y$")
    vendor_identifier: str = Field(min_length=1)
    parameter_path: tuple[str, ...] = Field(min_length=1)
    response_aliases: tuple[str, ...]


class GovernmentBondIdentityContract(FrozenModel):
    vendor_identifier: str = Field(min_length=1)
    response_aliases: tuple[str, ...]


def validate_government_bond_request_identities(
    registry: DirectBindingRegistry, compiled: CompiledSuite
) -> None:
    cases = {str(case.case_id): case for case in compiled.cases}
    access_paths = {str(path.access_path_id): path for path in compiled.access_paths}
    for binding in registry.bindings:
        case = cases[str(binding.case_id)]
        qualification = access_paths[str(binding.access_path_id)].qualification
        if (
            qualification is None
            or binding.source_digest != qualification.evidence_digest
        ):
            raise DirectBindingRegistryError(
                "binding source digest does not match Access Path qualification"
            )
        try:
            identity = GovernmentBondRequestIdentity.model_validate(
                binding.request_identity
            )
        except ValueError as exc:
            raise DirectBindingRegistryError(
                "government-bond binding requires a valid request identity"
            ) from exc
        if identity.country != case.input.get(
            "country"
        ) or identity.tenor != case.input.get("tenor"):
            raise DirectBindingRegistryError(
                "government-bond request identity does not match frozen case"
            )
        contracts = case.input.get("provider_identities")
        if not isinstance(contracts, dict):
            raise DirectBindingRegistryError(
                "government-bond case has no Provider identity contract"
            )
        try:
            contract = GovernmentBondIdentityContract.model_validate(
                contracts[str(binding.access_path_id)]
            )
        except (KeyError, ValueError) as exc:
            raise DirectBindingRegistryError(
                "government-bond binding has no canonical identity contract"
            ) from exc
        if (
            identity.vendor_identifier != contract.vendor_identifier
            or identity.response_aliases != contract.response_aliases
        ):
            raise DirectBindingRegistryError(
                "government-bond binding differs from canonical identity contract"
            )
        expected_path = (
            ("series_id",) if binding.provider_id == "stlouisfed-fred" else ("country",)
        )
        if identity.parameter_path != expected_path:
            raise DirectBindingRegistryError(
                "government-bond identity parameter path is not canonical"
            )
        if _parameter_value(binding.parameters, identity.parameter_path) != (
            identity.vendor_identifier
        ):
            raise DirectBindingRegistryError(
                "binding identity parameter does not equal the vendor identifier"
            )
        if binding.parameters.get("tenor", "10Y") != identity.tenor:
            raise DirectBindingRegistryError(
                "binding tenor does not match request identity"
            )


def _parameter_value(parameters: dict[str, object], path: tuple[str, ...]) -> object:
    value: object = parameters
    for segment in path:
        if not isinstance(value, dict) or segment not in value:
            raise DirectBindingRegistryError(
                "binding identity parameter path is invalid"
            )
        value = value[segment]
    return value
