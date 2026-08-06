from __future__ import annotations

from pathlib import Path

import yaml

from qveris_bench.catalog.validation import validate_cap_file
from qveris_bench.suites.loader import load_cases, load_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs" / "stock_quote"


def test_ac1_stock_quote_pack_reuses_the_versioned_direct_contract() -> None:
    cap = validate_cap_file(PACK / "cap.yaml")
    suite = load_suite(PACK / "suite.yaml")
    cases = load_cases(PACK / "cases.yaml")

    assert (cap.cap_id, cap.version) == ("stock-quote", "1.0.0")
    assert suite.cap_id == cap.cap_id
    assert suite.cap_version == cap.version
    assert [mode.value for mode in suite.modes] == ["direct"]
    assert len(suite.access_path_ids) == 2
    assert {case.case_id for case in cases} == set(suite.case_ids)


def test_ac2_stock_quote_pack_has_success_and_negative_control() -> None:
    cases = {case.case_id: case for case in load_cases(PACK / "cases.yaml")}

    assert cases["aapl-quote"].input == {"symbol": "AAPL"}
    assert "price" in cases["aapl-quote"].completion_conditions
    assert cases["invalid-stock"].negative_control
    assert cases["invalid-stock"].completion_conditions == ("validation_error",)


def test_ac3_stock_quote_bindings_are_exactly_two_official_candidates() -> None:
    data = yaml.safe_load((PACK / "provider-bindings.yaml").read_text())
    bindings = data["access_paths"]

    assert len(bindings) == 2
    assert len({binding["provider_id"] for binding in bindings}) == 2
    assert len({binding["access_path_id"] for binding in bindings}) == 2
    assert all(
        binding["official_source"].startswith("https://") for binding in bindings
    )


def test_ac4_stock_quote_outcomes_remain_categorical() -> None:
    rules = yaml.safe_load((PACK / "outcome-rules.yaml").read_text())

    assert rules["completion_requires"] == ["symbol", "price"]
    assert rules["negative_control_requires"] == ["validation_error"]
