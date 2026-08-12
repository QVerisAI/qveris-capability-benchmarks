import hashlib
from pathlib import Path

import yaml

from qveris_bench.execution.direct_binding import (
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"
MARKETS = {"US", "HK", "CN", "JP", "DE", "FR", "BR", "IN", "ES"}


def _compiled():
    return compile_suite(
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
    )


def test_ac1_market_suite_freezes_nine_markets_two_rounds_and_66_calls() -> None:
    compiled = _compiled()
    positive = [case for case in compiled.cases if not case.negative_control]
    applicable = [cell for cell in compiled.run_plan.cells if cell.applicable]

    assert {str(case.input["market"]) for case in positive} == MARKETS
    assert compiled.suite.rounds == 2
    assert len(compiled.run_plan.cells) == 120
    assert len(applicable) == 66
    cases = {case.case_id: case for case in compiled.cases}
    assert sum(not cases[cell.case_id].negative_control for cell in applicable) == 54


def test_ac2_only_explicit_contract_or_qveris_unsupported_cells_are_skipped() -> None:
    compiled = _compiled()
    cases = {str(case.case_id): case for case in compiled.cases}
    skipped = {
        (str(cell.access_path_id), str(cases[str(cell.case_id)].input["market"]))
        for cell in compiled.run_plan.cells
        if not cell.applicable and not cases[str(cell.case_id)].negative_control
    }

    assert skipped == {
        *(
            ("alpha-vantage-dividends-qveris", market)
            for market in {"HK", "JP", "DE", "BR", "IN"}
        ),
        *(("hangseng-dividends-qveris", market) for market in MARKETS - {"CN"}),
        *(("massive-stocks-dividends-qveris", market) for market in MARKETS - {"US"}),
        *(("ifind-native-mcp", market) for market in MARKETS - {"US", "HK", "CN"}),
    }
    assert all(
        cell.applicability_reason
        and (
            "QVeris preflight" in cell.applicability_reason
            or "Access Path contract" in cell.applicability_reason
        )
        for cell in compiled.run_plan.cells
        if not cell.applicable and not cases[str(cell.case_id)].negative_control
    )
    preflight_path = PACK / "market-preflight.yaml"
    preflight = yaml.safe_load(preflight_path.read_text(encoding="utf-8"))
    declared = {
        (decision["access_path_id"], market)
        for decision in preflight["decisions"]
        for market in decision["markets"]
    }
    assert declared == skipped
    assert compiled.suite.environment["preflight_digest"] == (
        "sha256:" + hashlib.sha256(preflight_path.read_bytes()).hexdigest()
    )


def test_ac3_every_applicable_cell_has_a_reproducible_request_identity() -> None:
    registry = load_direct_binding_registry(PACK / "market-direct-bindings.json")
    validate_direct_binding_registry(
        registry,
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        cap_path=PACK / "cap.yaml",
    )
    compiled = _compiled()
    applicable = {
        (str(cell.case_id), str(cell.access_path_id))
        for cell in compiled.run_plan.cells
        if cell.applicable
    }

    assert len(registry.bindings) == 33
    assert {
        (str(binding.case_id), str(binding.access_path_id))
        for binding in registry.bindings
    } == applicable
    for binding in registry.bindings:
        if "invalid" in str(binding.case_id):
            continue
        assert binding.request_identity is not None
        assert binding.request_identity.market in MARKETS
        assert binding.request_identity.vendor_symbol


def test_ac4_harbor_sv_is_not_a_market_result_source() -> None:
    selection = (
        ROOT / "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.yaml"
    ).read_text(encoding="utf-8")

    assert "market_coverage_release" in selection
    assert "qveris_sv" not in selection


def test_ac5_live_workflow_executes_every_applicable_binding_twice() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/live-dividend-market-coverage-e2e.yml").read_text(
            encoding="utf-8"
        )
    )
    matrix = workflow["jobs"]["direct"]["strategy"]["matrix"]
    registry = load_direct_binding_registry(PACK / "market-direct-bindings.json")

    assert matrix["round"] == [1, 2]
    assert set(matrix["binding_id"]) == {
        str(binding.binding_id) for binding in registry.bindings
    }
    assert len(matrix["binding_id"]) * len(matrix["round"]) == 66
