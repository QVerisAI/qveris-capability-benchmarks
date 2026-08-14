from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qveris_bench.cap_packs.govt_bond_yield.models import (
    validate_government_bond_request_identities,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import (
    DirectBindingRegistryError,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/govt-bond-yield"
MARKETS = {"US", "CN", "UK", "DE", "JP", "AU", "CA"}
PATHS = {
    "stlouisfed-fred-govt-bond-yield-qveris",
    "qveris-finance-govt-bond-yield-qveris",
}


def _yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _compile(prefix: str):
    suite_name = "suite.yaml" if prefix == "baseline" else "market-suite.yaml"
    cases_name = "cases.yaml" if prefix == "baseline" else "market-cases.yaml"
    return compile_suite(
        PACK / suite_name,
        PACK / cases_name,
        PACK / "providers",
        PACK / "cap.yaml",
        ROOT / "harbor_catalog/contracts.json",
    )


def test_ac1_freezes_exact_harbor_contract() -> None:
    compiled = _compile("baseline")
    source = compiled.run_plan.cap_sources[0]

    assert source.harbor_capability_id == "RATES.GOVT_BENCHMARK"
    assert source.contract_version == 1
    assert source.catalog_snapshot_digest == (
        "e30cafae2a5001ae312f70c727b2b826ff48400f8924c893b8e874d09cfd2fbe"
    )
    assert source.contract_digest == (
        "0123f6f71e22364cfe8c11828e3a39d757ef7488f709cd503f0fc07b8cbd2004"
    )


def test_ac2_candidate_dispositions_equal_the_frozen_source_set() -> None:
    dispositions = _yaml(PACK / "candidate-dispositions.yaml")
    manifest_path = PACK / str(dispositions["source_manifest"])
    manifest = _yaml(manifest_path)

    assert dispositions["source_manifest_digest"] == sha256_digest(
        manifest_path.read_bytes()
    )
    source_candidates = {
        tuple(str(value).split("|", 1)) for value in manifest["candidates"]
    }
    rows = dispositions["candidates"]
    assert isinstance(rows, list)
    disposition_candidates = {
        (str(row["source_provider_id"]), str(row["tool_id"])) for row in rows
    }
    assert source_candidates == disposition_candidates
    assert len(rows) == 3
    assert {str(row["disposition"]) for row in rows} == {"included", "excluded"}
    alpha = next(row for row in rows if row["source_provider_id"] == "alphavantage")
    assert alpha["disposition"] == "excluded"
    assert all(row.get("reason") and row.get("evidence_digest") for row in rows)


def test_ac3_compiles_two_round_baseline_and_market_matrix() -> None:
    baseline = _compile("baseline")
    market = _compile("market")
    baseline_cases = {case.case_id: case for case in baseline.cases}
    positive = [case for case in market.cases if not case.negative_control]

    assert baseline.suite.rounds == market.suite.rounds == 2
    assert {str(case.input["country"]) for case in positive} == MARKETS
    assert any(case.negative_control for case in baseline_cases.values())
    assert set(baseline.suite.access_path_ids) == PATHS
    assert set(market.suite.access_path_ids) == PATHS


def test_ac3_bounds_real_execute_calls() -> None:
    baseline = _compile("baseline")
    market = _compile("market")
    applicable = [
        cell
        for compiled in (baseline, market)
        for cell in compiled.run_plan.cells
        if cell.applicable
    ]

    assert len(applicable) == 36


def test_ac4_every_applicable_cell_has_one_frozen_direct_binding() -> None:
    for prefix in ("baseline", "market"):
        suite_name = "suite.yaml" if prefix == "baseline" else "market-suite.yaml"
        cases_name = "cases.yaml" if prefix == "baseline" else "market-cases.yaml"
        registry_name = (
            "direct-bindings.json"
            if prefix == "baseline"
            else "market-direct-bindings.json"
        )
        registry = load_direct_binding_registry(PACK / registry_name)
        validate_direct_binding_registry(
            registry,
            PACK / suite_name,
            PACK / cases_name,
            PACK / "providers",
            cap_path=PACK / "cap.yaml",
        )
        compiled = _compile(prefix)
        validate_government_bond_request_identities(registry, compiled)
        assert all(
            binding.request_identity is not None for binding in registry.bindings
        )


def test_ac4_rejects_binding_owned_country_or_alias_identity() -> None:
    registry = load_direct_binding_registry(PACK / "market-direct-bindings.json")
    compiled = _compile("market")
    au_index = next(
        index
        for index, binding in enumerate(registry.bindings)
        if binding.binding_id == "fred-au-10y-market"
    )
    au = registry.bindings[au_index]
    identity = dict(au.request_identity or {})
    identity["vendor_identifier"] = "IRLTLT01CAM156N"
    tampered_bindings = list(registry.bindings)
    tampered_bindings[au_index] = au.model_copy(
        update={
            "parameters": {**au.parameters, "series_id": "IRLTLT01CAM156N"},
            "request_identity": identity,
        }
    )

    with pytest.raises(
        DirectBindingRegistryError,
        match="canonical identity contract",
    ):
        validate_government_bond_request_identities(
            registry.model_copy(update={"bindings": tuple(tampered_bindings)}),
            compiled,
        )

    qf_index = next(
        index
        for index, binding in enumerate(registry.bindings)
        if binding.binding_id == "qveris-finance-au-10y-market"
    )
    qf = registry.bindings[qf_index]
    qf_identity = dict(qf.request_identity or {})
    qf_identity["response_aliases"] = [
        *qf_identity["response_aliases"],
        "10-Year Treasury Constant Maturity Rate",
    ]
    tampered_bindings = list(registry.bindings)
    tampered_bindings[qf_index] = qf.model_copy(
        update={"request_identity": qf_identity}
    )

    with pytest.raises(
        DirectBindingRegistryError,
        match="canonical identity contract",
    ):
        validate_government_bond_request_identities(
            registry.model_copy(update={"bindings": tuple(tampered_bindings)}),
            compiled,
        )


def test_ac4_rejects_binding_source_digest_drift() -> None:
    registry = load_direct_binding_registry(PACK / "direct-bindings.json")
    first = registry.bindings[0].model_copy(
        update={"source_digest": "sha256:" + "0" * 64}
    )
    tampered = registry.model_copy(update={"bindings": (first, *registry.bindings[1:])})

    with pytest.raises(DirectBindingRegistryError, match="source digest"):
        validate_government_bond_request_identities(tampered, _compile("baseline"))


def test_ac5_question_bank_promotes_only_the_selected_cap() -> None:
    bank = _yaml(ROOT / "question_bank/capabilities.yaml")
    capabilities = bank["capabilities"]
    assert isinstance(capabilities, list)
    selected = next(
        item for item in capabilities if item["cap_id"] == "govt-bond-yield"
    )

    assert selected["lifecycle"] == "runnable"
    assert selected["harbor_capability_id"] == "RATES.GOVT_BENCHMARK"
