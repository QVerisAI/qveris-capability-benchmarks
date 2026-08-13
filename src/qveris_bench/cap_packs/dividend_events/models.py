from __future__ import annotations

from pydantic import Field

from qveris_bench.execution.direct_binding import (
    DirectBindingRegistry,
    DirectBindingRegistryError,
)
from qveris_bench.models.base import FrozenModel
from qveris_bench.suites.compiler import CompiledSuite


class DividendRequestIdentity(FrozenModel):
    market: str = Field(pattern=r"^[A-Z]{2,8}$")
    canonical_symbol: str = Field(min_length=1)
    vendor_symbol: str = Field(min_length=1)


class PublicDividendFacts(FrozenModel):
    symbol: str | None = None
    effective_date: str | None = None
    amount: float | int | None = None
    currency: str | None = None
    payment_date: str | None = None
    declaration_date: str | None = None
    record_date: str | None = None
    event_count: float | int | None = None
    identity_verified: bool | None = None
    identity_basis: str | None = None
    returned_symbol: str | None = None
    validation_error: str | None = None


def dividend_request_identity(value: object) -> DividendRequestIdentity | None:
    if value is None:
        return None
    return DividendRequestIdentity.model_validate(value)


def validate_dividend_request_identities(
    registry: DirectBindingRegistry, compiled: CompiledSuite
) -> None:
    cases = {case.case_id: case for case in compiled.cases}
    for binding in registry.bindings:
        case = cases[binding.case_id]
        market = case.input.get("market")
        if market is None:
            continue
        try:
            identity = DividendRequestIdentity.model_validate(binding.request_identity)
        except ValueError as exc:
            raise DirectBindingRegistryError(
                "market Direct binding requires a valid request identity"
            ) from exc
        if identity.market != market or identity.canonical_symbol != case.input.get(
            "symbol"
        ):
            raise DirectBindingRegistryError(
                "binding request identity does not match frozen case"
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
