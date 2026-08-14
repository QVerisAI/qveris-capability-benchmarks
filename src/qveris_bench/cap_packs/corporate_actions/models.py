from __future__ import annotations

from pydantic import Field

from qveris_bench.execution.direct_binding import (
    DirectBindingRegistry,
    DirectBindingRegistryError,
)
from qveris_bench.models.base import FrozenModel
from qveris_bench.suites.compiler import CompiledSuite


class CorporateActionRequestIdentity(FrozenModel):
    market: str = Field(pattern=r"^[A-Z]{2,8}$")
    canonical_symbol: str = Field(min_length=1)
    vendor_symbol: str = Field(min_length=1)
    parameter_path: tuple[str, ...] = Field(min_length=1)


def corporate_action_request_identity(
    value: object,
) -> CorporateActionRequestIdentity | None:
    if value is None:
        return None
    return CorporateActionRequestIdentity.model_validate(value)


def validate_corporate_action_request_identities(
    registry: DirectBindingRegistry, compiled: CompiledSuite
) -> None:
    cases = {case.case_id: case for case in compiled.cases}
    for binding in registry.bindings:
        case = cases[binding.case_id]
        market = case.input.get("market")
        if market is None:
            continue
        try:
            identity = CorporateActionRequestIdentity.model_validate(
                binding.request_identity
            )
        except ValueError as exc:
            raise DirectBindingRegistryError(
                "corporate-action binding requires a valid request identity"
            ) from exc
        if identity.market != market or identity.canonical_symbol != case.input.get(
            "symbol"
        ):
            raise DirectBindingRegistryError(
                "corporate-action request identity does not match frozen case"
            )
        expected_path = (
            ("ticker",) if binding.provider_id == "massive-stocks" else ("symbol",)
        )
        if identity.parameter_path != expected_path:
            raise DirectBindingRegistryError(
                "corporate-action identity parameter path is not canonical"
            )
        if _symbol_code(identity.vendor_symbol) != _symbol_code(
            identity.canonical_symbol
        ):
            raise DirectBindingRegistryError(
                "vendor symbol does not identify the frozen canonical symbol"
            )
        if _parameter_value(binding.parameters, identity.parameter_path) != (
            identity.vendor_symbol
        ):
            raise DirectBindingRegistryError(
                "binding identity parameter does not equal the vendor symbol"
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


def _symbol_code(value: str) -> str:
    code = value.strip().upper().split(":", 1)[0].split(".", 1)[0].lstrip("0")
    return code or "0"
