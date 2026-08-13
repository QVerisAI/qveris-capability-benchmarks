from pathlib import Path

import pytest

from qveris_bench.execution.direct_binding import (
    DirectBindingRegistryError,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"
REGISTRY = PACK / "direct-bindings.json"


def test_ac6_registry_binds_every_applicable_cell_identity_once() -> None:
    registry = load_direct_binding_registry(REGISTRY)
    validate_direct_binding_registry(
        registry,
        PACK / "suite.yaml",
        PACK / "cases.yaml",
        ROOT / "providers",
    )
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )

    expected = {
        (str(cell.case_id), str(cell.access_path_id))
        for cell in compiled.run_plan.cells
        if cell.applicable
    }
    actual = {
        (str(binding.case_id), str(binding.access_path_id))
        for binding in registry.bindings
    }
    assert len(registry.bindings) == 12
    assert actual == expected


def test_ac6_ifind_binding_is_native_mcp_only() -> None:
    registry = load_direct_binding_registry(REGISTRY)
    ifind = [binding for binding in registry.bindings if binding.provider_id == "ifind"]

    assert len(ifind) == 2
    assert {binding.transport.value for binding in ifind} == {"native_mcp"}
    assert {binding.tool_id for binding in ifind} == {"get_stock_events"}


def test_ac6_hangseng_binding_maps_canonical_symbol_to_numeric_provider_code() -> None:
    registry = load_direct_binding_registry(REGISTRY)
    positive = next(
        binding
        for binding in registry.bindings
        if binding.binding_id == "hangseng-cn-600519-dividends"
    )

    assert positive.parameters["stockObject"] == ["600519"]


def test_ac6_registry_rejects_transport_or_identity_redirection() -> None:
    registry = load_direct_binding_registry(REGISTRY)
    original = registry.bindings[0]

    redirected_transport = registry.model_copy(
        update={
            "bindings": (
                original.model_copy(update={"transport": "qveris_connector"}),
                *registry.bindings[1:],
            )
        }
    )
    with pytest.raises(DirectBindingRegistryError, match="transport"):
        validate_direct_binding_registry(
            redirected_transport,
            PACK / "suite.yaml",
            PACK / "cases.yaml",
            ROOT / "providers",
        )

    redirected_case = registry.model_copy(
        update={
            "bindings": (
                original.model_copy(update={"case_id": "invalid-dividend-symbol"}),
                *registry.bindings[1:],
            )
        }
    )
    with pytest.raises(DirectBindingRegistryError, match="cell identities"):
        validate_direct_binding_registry(
            redirected_case,
            PACK / "suite.yaml",
            PACK / "cases.yaml",
            ROOT / "providers",
        )
