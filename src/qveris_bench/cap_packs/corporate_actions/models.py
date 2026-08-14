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
        if not _contains_value(binding.parameters, identity.vendor_symbol):
            raise DirectBindingRegistryError(
                "binding parameters do not contain the vendor symbol"
            )


def _contains_value(value: object, expected: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(_contains_value(item, expected) for item in value)
    if isinstance(value, str):
        return expected in value
    return False
