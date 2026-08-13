from __future__ import annotations

from pathlib import Path

from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]


def test_corporate_actions_pack_freezes_four_qveris_paths_and_three_rounds() -> None:
    compiled = compile_suite(
        ROOT / "cap_packs" / "corporate-actions" / "suite.yaml",
        ROOT / "cap_packs" / "corporate-actions" / "cases.yaml",
        ROOT / "providers",
        ROOT / "cap_packs" / "corporate-actions" / "cap.yaml",
        ROOT / "harbor_catalog" / "contracts.json",
    )

    assert (
        compiled.run_plan.cap_sources[0].harbor_capability_id
        == "MKT.CORPORATE_ACTIONS"
    )
    assert {cell.round for cell in compiled.run_plan.cells} == {1, 2, 3}
    assert {
        (cell.provider_id, cell.access_path_id)
        for cell in compiled.run_plan.cells
    } == {
        ("alpha-vantage", "alpha-vantage-corporate-actions-qveris"),
        ("eodhd", "eodhd-corporate-actions-qveris"),
        ("massive-stocks", "massive-stocks-corporate-actions-qveris"),
        ("twelve-data", "twelve-data-corporate-actions-qveris"),
    }
    assert len(compiled.run_plan.cells) == 24


def test_corporate_actions_authorization_does_not_mutate_global_path_qualification(
) -> None:
    registry = ProviderRegistryRepository(ROOT / "providers").list()
    selected = {
        path.access_path_id: path.qualification.disposition.value
        for record in registry
        for path in record.access_paths
        if path.access_path_id.endswith("corporate-actions-qveris")
    }

    assert selected == {
        "alpha-vantage-corporate-actions-qveris": "excluded",
        "eodhd-corporate-actions-qveris": "excluded",
        "massive-stocks-corporate-actions-qveris": "excluded",
        "twelve-data-corporate-actions-qveris": "excluded",
    }
