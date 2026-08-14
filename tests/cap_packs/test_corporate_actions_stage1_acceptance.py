from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qveris_bench.cap_packs.corporate_actions.models import (
    validate_corporate_action_request_identities,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.direct_binding import (
    DirectBindingRegistryError,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/corporate-actions/v2"
MARKETS = {"US", "HK", "CN", "JP", "DE", "FR", "BR", "IN", "ES"}
SOURCE_SNAPSHOT_DIGEST = (
    "sha256:7579d22a0e6a552f5c1225e5e208a0834fca8173c5b8253d949eb96d294cf7a4"
)


def _yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _compile(suite: str, cases: str):
    return compile_suite(
        PACK / suite,
        PACK / cases,
        ROOT / "providers",
        PACK / "cap.yaml",
        ROOT / "harbor_catalog/contracts.json",
    )


def test_ac1_v2_keeps_exact_harbor_contract_provenance() -> None:
    compiled = _compile("baseline-suite.yaml", "baseline-cases.yaml")
    source = compiled.run_plan.cap_sources[0]

    assert source.harbor_capability_id == "MKT.CORPORATE_ACTIONS"
    assert source.contract_version == 1
    assert source.catalog_snapshot_digest == (
        "e30cafae2a5001ae312f70c727b2b826ff48400f8924c893b8e874d09cfd2fbe"
    )
    assert source.contract_digest == (
        "70d5687f6cdb493df3d8af69fc38f8fb41d027139c423bf3018b861f593b3f8d"
    )


def test_ac2_private_candidate_snapshot_has_terminal_dispositions() -> None:
    document = _yaml(PACK / "candidate-dispositions.yaml")
    source_manifest = _yaml(PACK / str(document["source_manifest"]))
    assert document["source_manifest_digest"] == sha256_digest(
        (PACK / str(document["source_manifest"])).read_bytes()
    )
    source = document["source_snapshot"]
    assert isinstance(source, dict)
    assert source == {
        "digest": SOURCE_SNAPSHOT_DIGEST,
        "row_count": 55,
        "provider_identity_count": 12,
    }
    candidates = document["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 55
    assert len({item["tool_id"] for item in candidates}) == 55
    assert len({item["source_provider_id"] for item in candidates}) == 12
    source_candidates = {
        tuple(str(value).split("|", 1)) for value in source_manifest["candidates"]
    }
    disposition_candidates = {
        (str(item["source_provider_id"]), str(item["tool_id"])) for item in candidates
    }
    assert source_manifest["source_snapshot_digest"] == SOURCE_SNAPSHOT_DIGEST
    assert source_manifest["row_count"] == 55
    assert source_manifest["provider_identity_count"] == 12
    assert source_candidates == disposition_candidates
    assert all(
        item["disposition"] in {"included", "excluded", "not_applicable"}
        and item.get("reason")
        and item.get("evidence_digest")
        for item in candidates
    )


def test_ac3_baseline_freezes_positive_and_negative_cases_for_three_rounds() -> None:
    compiled = _compile("baseline-suite.yaml", "baseline-cases.yaml")
    cases = {case.case_id: case for case in compiled.cases}

    assert compiled.suite.rounds == 3
    assert any(not case.negative_control for case in cases.values())
    assert any(case.negative_control for case in cases.values())
    assert all(
        {cell.round for cell in compiled.run_plan.cells if cell.case_id == case_id}
        == {1, 2, 3}
        for case_id in cases
    )


def test_ac4_market_suite_freezes_nine_markets_and_two_rounds() -> None:
    compiled = _compile("market-suite.yaml", "market-cases.yaml")
    positive = [case for case in compiled.cases if not case.negative_control]

    assert {str(case.input["market"]) for case in positive} == MARKETS
    assert len(positive) == 9
    assert compiled.suite.rounds == 2


def test_ac5_only_evidence_bound_market_cells_are_not_applicable() -> None:
    compiled = _compile("market-suite.yaml", "market-cases.yaml")
    cases = {case.case_id: case for case in compiled.cases}
    preflight = _yaml(PACK / "market-preflight.yaml")
    decisions = preflight["decisions"]
    assert isinstance(decisions, list)
    declared = {
        (decision["access_path_id"], market)
        for decision in decisions
        for market in decision["markets"]
    }
    skipped = {
        (cell.access_path_id, str(cases[cell.case_id].input["market"]))
        for cell in compiled.run_plan.cells
        if not cell.applicable and not cases[cell.case_id].negative_control
    }

    assert skipped == declared
    assert all(
        decision.get("basis") in {"access_path_contract", "qveris_preflight"}
        and decision.get("evidence_digest")
        for decision in decisions
    )


def test_ac6_every_applicable_cell_has_one_frozen_direct_binding() -> None:
    for prefix in ("baseline", "market"):
        suite = PACK / f"{prefix}-suite.yaml"
        cases = PACK / f"{prefix}-cases.yaml"
        registry = load_direct_binding_registry(PACK / f"{prefix}-direct-bindings.json")
        validate_direct_binding_registry(
            registry,
            suite,
            cases,
            ROOT / "providers",
            cap_path=PACK / "cap.yaml",
        )
        compiled = _compile(f"{prefix}-suite.yaml", f"{prefix}-cases.yaml")
        validate_corporate_action_request_identities(registry, compiled)
        assert all(
            binding.request_identity
            for binding in registry.bindings
            if "invalid" not in binding.case_id
        )


@pytest.mark.parametrize(
    ("identity_update", "parameters"),
    [
        ({"market": "HK"}, None),
        ({"canonical_symbol": "MSFT"}, None),
        ({}, {"symbol": "MSFT"}),
    ],
)
def test_ac6_rejects_request_identity_drift(
    identity_update: dict[str, str], parameters: dict[str, object] | None
) -> None:
    registry = load_direct_binding_registry(PACK / "baseline-direct-bindings.json")
    compiled = _compile("baseline-suite.yaml", "baseline-cases.yaml")
    binding = next(item for item in registry.bindings if "invalid" not in item.case_id)
    identity = dict(binding.request_identity or {})
    identity.update(identity_update)
    changed = binding.model_copy(
        update={
            "request_identity": identity,
            "parameters": parameters or binding.parameters,
        }
    )
    mutated = registry.model_copy(
        update={
            "bindings": tuple(
                changed if item.binding_id == binding.binding_id else item
                for item in registry.bindings
            )
        }
    )

    with pytest.raises(DirectBindingRegistryError):
        validate_corporate_action_request_identities(mutated, compiled)


def test_ac7_live_workflows_match_frozen_bindings_and_rounds() -> None:
    for prefix, rounds in (("baseline", [1, 2, 3]), ("market", [1, 2])):
        workflow = _yaml(
            ROOT / ".github/workflows" / f"live-corporate-actions-{prefix}-e2e.yml"
        )
        matrix = workflow["jobs"]["direct"]["strategy"]["matrix"]
        registry = load_direct_binding_registry(PACK / f"{prefix}-direct-bindings.json")

        assert matrix["round"] == rounds
        assert set(matrix["binding_id"]) == {
            str(binding.binding_id) for binding in registry.bindings
        }


def test_ac13_stage_one_manifest_forbids_article_outputs() -> None:
    document = _yaml(PACK / "stage-one-manifest.yaml")

    assert document["stage"] == "test_and_evidence"
    assert document["article_generation"] == "forbidden"
    assert not any("docs/guides" in path for path in document["allowed_output_roots"])
